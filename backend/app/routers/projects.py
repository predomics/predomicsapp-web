"""Project management endpoints with database and auth."""

import io

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.database import get_db
from ..core.deps import get_current_user
from ..models.db_models import User, Project, Dataset
from ..models.schemas import ProjectInfo, DatasetInfo, DatasetRef
from ..services import storage

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("/", response_model=ProjectInfo)
async def create_project(
    name: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new project."""
    project = Project(name=name, user_id=user.id)
    db.add(project)
    await db.flush()

    # Create filesystem directories
    storage.ensure_project_dirs(project.id)

    return ProjectInfo(
        project_id=project.id,
        name=project.name,
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
        .options(selectinload(Project.datasets), selectinload(Project.jobs))
        .order_by(Project.created_at.desc())
    )
    projects = result.scalars().all()
    return [
        ProjectInfo(
            project_id=p.id,
            name=p.name,
            created_at=p.created_at.isoformat(),
            datasets=[DatasetRef(id=d.id, filename=d.filename, path=d.disk_path) for d in p.datasets],
            jobs=[j.id for j in p.jobs],
        )
        for p in projects
    ]


@router.get("/{project_id}", response_model=ProjectInfo)
async def get_project(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get project details (must be owned by current user)."""
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id, Project.user_id == user.id)
        .options(selectinload(Project.datasets), selectinload(Project.jobs))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectInfo(
        project_id=project.id,
        name=project.name,
        created_at=project.created_at.isoformat(),
        datasets=[DatasetRef(id=d.id, filename=d.filename, path=d.disk_path) for d in project.datasets],
        jobs=[j.id for j in project.jobs],
    )


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a project and all its data."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

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
    """Upload a dataset (TSV/CSV) to a project."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    content = await file.read()

    # Create dataset record
    dataset = Dataset(project_id=project_id, filename=file.filename, disk_path="")
    db.add(dataset)
    await db.flush()

    # Save file to disk
    disk_path = storage.save_dataset_file(project_id, dataset.id, file.filename, content)
    dataset.disk_path = disk_path

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
