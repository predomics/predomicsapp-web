"""Sample/demo dataset endpoints — lets any user load bundled demo data."""

from __future__ import annotations

import io

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.config import settings
from ..core.database import get_db
from ..core.deps import get_current_user
from ..models.db_models import User, Project, Dataset
from ..models.schemas import ProjectInfo, DatasetRef
from ..services import storage

router = APIRouter(prefix="/samples", tags=["samples"])

# Datasets bundled with the app
SAMPLE_DATASETS = {
    "qin2014_cirrhosis": {
        "name": "Qin2014 Liver Cirrhosis",
        "description": "Qin N et al., Nature 2014 — 1,980 MSP features, 180 train + 30 test samples",
        "files": [
            {"filename": "Xtrain.tsv", "features_in_rows": True},
            {"filename": "Ytrain.tsv", "features_in_rows": False},
            {"filename": "Xtest.tsv", "features_in_rows": True},
            {"filename": "Ytest.tsv", "features_in_rows": False},
        ],
    },
}


@router.get("/")
async def list_samples():
    """List available sample datasets."""
    result = []
    for key, info in SAMPLE_DATASETS.items():
        sample_dir = settings.sample_dir if key == "qin2014_cirrhosis" else settings.data_dir / key
        available = sample_dir.exists()
        result.append({
            "id": key,
            "name": info["name"],
            "description": info["description"],
            "available": available,
            "files": [f["filename"] for f in info["files"]],
        })
    return result


@router.post("/{sample_id}/load", response_model=ProjectInfo)
async def load_sample(
    sample_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a project and load a sample dataset into it for the current user.

    If the user already has a project loaded from this sample, return the
    existing project instead of creating a duplicate.
    """
    if sample_id not in SAMPLE_DATASETS:
        raise HTTPException(status_code=404, detail="Sample dataset not found")

    sample = SAMPLE_DATASETS[sample_id]
    sample_dir = settings.sample_dir if sample_id == "qin2014_cirrhosis" else settings.data_dir / sample_id

    if not sample_dir.exists():
        raise HTTPException(status_code=404, detail="Sample data files not found on disk")

    # Check if user already has a project from this sample
    existing = await db.execute(
        select(Project)
        .where(Project.user_id == user.id, Project.name == sample["name"])
        .options(selectinload(Project.datasets), selectinload(Project.jobs))
    )
    existing_project = existing.scalars().first()
    if existing_project:
        return ProjectInfo(
            project_id=existing_project.id,
            name=existing_project.name,
            created_at=existing_project.created_at.isoformat(),
            datasets=[
                DatasetRef(id=d.id, filename=d.filename, path=d.disk_path)
                for d in existing_project.datasets
            ],
            jobs=[],
        )

    # Create project
    project = Project(name=sample["name"], user_id=user.id)
    db.add(project)
    await db.flush()
    storage.ensure_project_dirs(project.id)

    # Load each file
    datasets = []
    for file_info in sample["files"]:
        filepath = sample_dir / file_info["filename"]
        if not filepath.exists():
            continue

        content = filepath.read_bytes()

        dataset = Dataset(project_id=project.id, filename=file_info["filename"], disk_path="")
        db.add(dataset)
        await db.flush()

        disk_path = storage.save_dataset_file(project.id, dataset.id, file_info["filename"], content)
        dataset.disk_path = disk_path

        datasets.append(DatasetRef(id=dataset.id, filename=file_info["filename"], path=disk_path))

    return ProjectInfo(
        project_id=project.id,
        name=project.name,
        created_at=project.created_at.isoformat(),
        datasets=datasets,
        jobs=[],
    )
