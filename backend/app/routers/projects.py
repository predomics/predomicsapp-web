"""Project management endpoints."""

from fastapi import APIRouter, HTTPException, UploadFile, File
from ..models.schemas import ProjectInfo, DatasetInfo
from ..services import storage

import pandas as pd
import io

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("/", response_model=ProjectInfo)
async def create_project(name: str):
    """Create a new project."""
    meta = storage.create_project(name)
    return ProjectInfo(**meta)


@router.get("/", response_model=list[ProjectInfo])
async def list_projects():
    """List all projects."""
    return [ProjectInfo(**m) for m in storage.list_projects()]


@router.get("/{project_id}", response_model=ProjectInfo)
async def get_project(project_id: str):
    """Get project details."""
    meta = storage.get_project(project_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectInfo(**meta)


@router.delete("/{project_id}")
async def delete_project(project_id: str):
    """Delete a project and all its data."""
    if not storage.delete_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return {"status": "deleted"}


@router.post("/{project_id}/datasets", response_model=DatasetInfo)
async def upload_dataset(
    project_id: str,
    file: UploadFile = File(...),
    features_in_rows: bool = True,
):
    """Upload a dataset (TSV/CSV) to a project."""
    meta = storage.get_project(project_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Project not found")

    content = await file.read()
    dataset_id = storage.save_dataset(project_id, file.filename, content)
    if not dataset_id:
        raise HTTPException(status_code=500, detail="Failed to save dataset")

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
