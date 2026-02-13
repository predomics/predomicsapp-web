"""File-based project and dataset storage."""

from __future__ import annotations
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..core.config import settings


def ensure_dirs() -> None:
    """Create storage directories if they don't exist."""
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.project_dir.mkdir(parents=True, exist_ok=True)


def create_project(name: str) -> dict:
    """Create a new project directory and return its metadata."""
    project_id = uuid.uuid4().hex[:12]
    project_path = settings.project_dir / project_id
    project_path.mkdir(parents=True)
    (project_path / "datasets").mkdir()
    (project_path / "jobs").mkdir()

    meta = {
        "project_id": project_id,
        "name": name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "datasets": [],
        "jobs": [],
    }
    with open(project_path / "meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    return meta


def get_project(project_id: str) -> dict | None:
    """Load project metadata."""
    meta_path = settings.project_dir / project_id / "meta.json"
    if not meta_path.exists():
        return None
    with open(meta_path) as f:
        return json.load(f)


def list_projects() -> list[dict]:
    """List all projects."""
    projects = []
    if not settings.project_dir.exists():
        return projects
    for p in sorted(settings.project_dir.iterdir()):
        meta_path = p / "meta.json"
        if meta_path.exists():
            with open(meta_path) as f:
                projects.append(json.load(f))
    return projects


def delete_project(project_id: str) -> bool:
    """Delete a project and all its data."""
    project_path = settings.project_dir / project_id
    if not project_path.exists():
        return False
    shutil.rmtree(project_path)
    return True


def save_dataset(project_id: str, filename: str, content: bytes) -> str:
    """Save an uploaded dataset file and return its ID."""
    project_path = settings.project_dir / project_id / "datasets"
    if not project_path.exists():
        return ""
    dataset_id = uuid.uuid4().hex[:8]
    dest = project_path / f"{dataset_id}_{filename}"
    dest.write_bytes(content)

    # Update project metadata
    meta = get_project(project_id)
    if meta:
        meta["datasets"].append({"id": dataset_id, "filename": filename, "path": str(dest)})
        with open(settings.project_dir / project_id / "meta.json", "w") as f:
            json.dump(meta, f, indent=2)

    return dataset_id


def get_dataset_path(project_id: str, dataset_id: str) -> Path | None:
    """Get the file path for a dataset."""
    datasets_dir = settings.project_dir / project_id / "datasets"
    if not datasets_dir.exists():
        return None
    for f in datasets_dir.iterdir():
        if f.name.startswith(dataset_id):
            return f
    return None


def save_job_result(project_id: str, job_id: str, results: dict) -> None:
    """Save job results to disk."""
    job_dir = settings.project_dir / project_id / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    with open(job_dir / "results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)


def get_job_result(project_id: str, job_id: str) -> dict | None:
    """Load job results from disk."""
    result_path = settings.project_dir / project_id / "jobs" / job_id / "results.json"
    if not result_path.exists():
        return None
    with open(result_path) as f:
        return json.load(f)
