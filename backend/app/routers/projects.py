"""Project management endpoints with database and auth."""

import io
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.database import get_db
from ..core.deps import get_current_user, get_project_with_access
from ..models.db_models import User, Project, Dataset, DatasetFile, ProjectDataset
from ..services import audit
from ..models.schemas import ProjectInfo, DatasetInfo, DatasetRef, DatasetFileRef
from ..services import storage
from .datasets import _infer_role

router = APIRouter(prefix="/projects", tags=["projects"])


def _build_project_info(project: Project) -> ProjectInfo:
    """Build ProjectInfo from a Project with loaded relationships."""
    datasets = []
    for link in project.dataset_links:
        ds = link.dataset
        files = [
            DatasetFileRef(id=f.id, filename=f.filename, role=f.role)
            for f in ds.files
        ]
        datasets.append(DatasetRef(id=ds.id, name=ds.name, files=files))

    job_count = len(project.jobs)
    share_count = len(project.shares) if project.shares else 0

    latest_job_status = None
    if project.jobs:
        sorted_jobs = sorted(project.jobs, key=lambda j: j.created_at, reverse=True)
        latest_job_status = sorted_jobs[0].status

    return ProjectInfo(
        project_id=project.id,
        name=project.name,
        description=project.description,
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat() if project.updated_at else None,
        datasets=datasets,
        jobs=[j.id for j in project.jobs],
        job_count=job_count,
        share_count=share_count,
        latest_job_status=latest_job_status,
    )


def _project_query_options():
    """Common selectinload options for project queries."""
    return [
        selectinload(Project.dataset_links)
            .selectinload(ProjectDataset.dataset)
            .selectinload(Dataset.files),
        selectinload(Project.jobs),
        selectinload(Project.shares),
    ]


@router.post("/", response_model=ProjectInfo)
async def create_project(
    name: str,
    description: str = "",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new project."""
    project = Project(name=name, description=description, user_id=user.id)
    db.add(project)
    await db.flush()

    # Create filesystem directories
    storage.ensure_project_dirs(project.id)
    await audit.log_action(db, user, audit.ACTION_PROJECT_CREATE, "project", project.id)

    return ProjectInfo(
        project_id=project.id,
        name=project.name,
        description=project.description,
        created_at=project.created_at.isoformat(),
        datasets=[],
        jobs=[],
    )


@router.get("/", response_model=list[ProjectInfo])
async def list_projects(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List projects owned by the current user."""
    result = await db.execute(
        select(Project)
        .where(Project.user_id == user.id)
        .options(*_project_query_options())
        .order_by(Project.created_at.desc())
    )
    projects = result.scalars().all()
    return [_build_project_info(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectInfo)
async def get_project(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get project details (owner or shared user)."""
    project, _ = await get_project_with_access(project_id, user, db, require_role="viewer")
    return _build_project_info(project)


@router.patch("/{project_id}", response_model=ProjectInfo)
async def update_project(
    project_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update project name and/or description (owner only)."""
    project, _ = await get_project_with_access(project_id, user, db, require_role="owner")
    if name is not None:
        project.name = name
    if description is not None:
        project.description = description
    project.updated_at = datetime.now(timezone.utc)
    return _build_project_info(project)


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a project (owner only). Datasets stay in user library."""
    project, _ = await get_project_with_access(project_id, user, db, require_role="owner")
    await audit.log_action(db, user, audit.ACTION_PROJECT_DELETE, "project", project_id)
    await db.delete(project)
    storage.delete_project_files(project_id)
    return {"status": "deleted"}


@router.post("/{project_id}/datasets", response_model=DatasetInfo)
async def upload_dataset(
    project_id: str,
    file: UploadFile = File(...),
    features_in_rows: bool = True,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a dataset file to a project (backward compat).

    Creates a dataset group in the user's library with one file,
    then assigns it to the project. Owner or editor access required.
    """
    project, _ = await get_project_with_access(project_id, user, db, require_role="editor")

    content = await file.read()

    # Create dataset group in user's library
    dataset = Dataset(name=file.filename, user_id=user.id)
    db.add(dataset)
    await db.flush()

    # Create file within the dataset group
    role = _infer_role(file.filename)
    ds_file = DatasetFile(
        dataset_id=dataset.id,
        filename=file.filename,
        role=role,
        disk_path="",
    )
    db.add(ds_file)
    await db.flush()

    # Save to user-level storage
    disk_path = storage.save_user_dataset_file(user.id, ds_file.id, file.filename, content)
    ds_file.disk_path = disk_path

    # Assign dataset group to project
    link = ProjectDataset(project_id=project_id, dataset_id=dataset.id)
    db.add(link)
    await db.flush()

    # Parse to get info
    try:
        sep = "\t" if file.filename.endswith(".tsv") else ","
        df = pd.read_csv(io.BytesIO(content), sep=sep, index_col=0)
        if features_in_rows:
            n_features, n_samples = df.shape
        else:
            n_samples, n_features = df.shape
    except Exception:
        n_features, n_samples = 0, 0

    return DatasetInfo(
        filename=file.filename,
        n_features=n_features,
        n_samples=n_samples,
        n_classes=0,
        features_in_rows=features_in_rows,
    )
