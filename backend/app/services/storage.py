"""Filesystem storage — handles file I/O only. Metadata lives in the database."""

from __future__ import annotations
import json
import shutil
from pathlib import Path

from ..core.config import settings


def ensure_dirs() -> None:
    """Create storage directories if they don't exist."""
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.project_dir.mkdir(parents=True, exist_ok=True)


def ensure_project_dirs(project_id: str) -> None:
    """Create project subdirectories on disk."""
    base = settings.project_dir / project_id
    (base / "datasets").mkdir(parents=True, exist_ok=True)
    (base / "jobs").mkdir(parents=True, exist_ok=True)


def save_dataset_file(project_id: str, dataset_id: str, filename: str, content: bytes) -> str:
    """Write dataset bytes to disk, return the file path."""
    dest = settings.project_dir / project_id / "datasets" / f"{dataset_id}_{filename}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    return str(dest)


def get_dataset_path(project_id: str, dataset_id: str) -> Path | None:
    """Get the file path for a dataset by prefix match."""
    datasets_dir = settings.project_dir / project_id / "datasets"
    if not datasets_dir.exists():
        return None
    for f in datasets_dir.iterdir():
        if f.name.startswith(dataset_id):
            return f
    return None


def delete_project_files(project_id: str) -> None:
    """Delete all files for a project from disk."""
    project_path = settings.project_dir / project_id
    if project_path.exists():
        shutil.rmtree(project_path)


def save_job_result(project_id: str, job_id: str, results: dict) -> str:
    """Save job results to disk, return the file path."""
    job_dir = settings.project_dir / project_id / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    result_path = job_dir / "results.json"
    with open(result_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    return str(result_path)


def get_job_result(project_id: str, job_id: str) -> dict | None:
    """Load job results from disk."""
    result_path = settings.project_dir / project_id / "jobs" / job_id / "results.json"
    if not result_path.exists():
        return None
    with open(result_path) as f:
        return json.load(f)
