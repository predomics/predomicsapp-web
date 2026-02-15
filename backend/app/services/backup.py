"""Backup and restore service — full system export/import as portable archives."""

import json
import logging
import shutil
import tarfile
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models.db_models import (
    User, Project, Dataset, DatasetFile, ProjectDataset,
    Job, ProjectShare, SchemaVersion,
)

_log = logging.getLogger(__name__)

BACKUP_DIR = Path(settings.data_dir) / "backups"

# Tables in FK dependency order (parents first).
TABLE_EXPORT_ORDER = [
    ("users", User),
    ("projects", Project),
    ("datasets", Dataset),
    ("dataset_files", DatasetFile),
    ("project_datasets", ProjectDataset),
    ("jobs", Job),
    ("project_shares", ProjectShare),
    ("schema_versions", SchemaVersion),
]


def ensure_backup_dir() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return BACKUP_DIR


def _serialize_row(obj) -> dict:
    """Convert an ORM object to a JSON-serializable dict."""
    data = {}
    for col in obj.__table__.columns:
        val = getattr(obj, col.name)
        if isinstance(val, datetime):
            val = val.isoformat()
        data[col.name] = val
    return data


async def create_backup(db: AsyncSession, description: str = "") -> dict:
    """Create a full system backup archive.

    The archive contains:
    - database/*.json  — one file per table
    - datasets/        — all user dataset files
    - projects/        — all job results and console logs
    - admin_defaults.json
    - manifest.json

    Returns metadata dict with backup_id, filename, size, table_counts.
    """
    ensure_backup_dir()
    backup_id = uuid.uuid4().hex[:12]
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    archive_name = f"predomics_backup_{timestamp}_{backup_id}.tar.gz"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # 1. Export all database tables as JSON
        db_dir = tmp / "database"
        db_dir.mkdir()
        table_counts = {}

        for table_name, model_cls in TABLE_EXPORT_ORDER:
            result = await db.execute(select(model_cls))
            rows = result.scalars().all()
            records = [_serialize_row(r) for r in rows]
            table_counts[table_name] = len(records)
            (db_dir / f"{table_name}.json").write_text(
                json.dumps(records, indent=2, default=str)
            )

        # 2. Copy dataset files
        datasets_src = Path(settings.data_dir) / "datasets"
        if datasets_src.is_dir():
            shutil.copytree(datasets_src, tmp / "datasets")

        # 3. Copy job results and logs
        if settings.project_dir.is_dir():
            shutil.copytree(settings.project_dir, tmp / "projects")

        # 4. Copy admin defaults
        defaults_path = Path(settings.data_dir) / "admin_defaults.json"
        if defaults_path.exists():
            shutil.copy2(defaults_path, tmp / "admin_defaults.json")

        # 5. Write manifest
        manifest = {
            "backup_id": backup_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "description": description,
            "app_version": "0.1.0",
            "table_counts": table_counts,
        }
        (tmp / "manifest.json").write_text(json.dumps(manifest, indent=2))

        # 6. Create tar.gz archive
        archive_path = BACKUP_DIR / archive_name
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(str(tmp), arcname="backup")

    size_bytes = archive_path.stat().st_size
    _log.info("Backup %s created: %s (%.1f MB)", backup_id, archive_name, size_bytes / 1e6)

    return {
        "backup_id": backup_id,
        "filename": archive_name,
        "size_bytes": size_bytes,
        "created_at": manifest["created_at"],
        "description": description,
        "table_counts": table_counts,
    }


def list_backups() -> list[dict]:
    """List all available backup archives with their manifests."""
    ensure_backup_dir()
    backups = []
    for f in sorted(BACKUP_DIR.glob("predomics_backup_*.tar.gz"), reverse=True):
        try:
            with tarfile.open(f, "r:gz") as tar:
                manifest_file = tar.extractfile("backup/manifest.json")
                manifest = json.loads(manifest_file.read())
                manifest["filename"] = f.name
                manifest["size_bytes"] = f.stat().st_size
                backups.append(manifest)
        except Exception as e:
            backups.append({
                "filename": f.name,
                "size_bytes": f.stat().st_size,
                "error": str(e),
            })
    return backups


def get_backup_path(backup_id: str) -> Optional[Path]:
    """Find the archive file for a given backup_id."""
    ensure_backup_dir()
    for f in BACKUP_DIR.glob(f"predomics_backup_*_{backup_id}.tar.gz"):
        return f
    return None


def delete_backup(backup_id: str) -> bool:
    """Delete a backup archive. Returns True if found and deleted."""
    path = get_backup_path(backup_id)
    if path and path.exists():
        path.unlink()
        return True
    return False


async def restore_backup(
    archive_path: Path,
    db: AsyncSession,
    mode: str = "replace",
) -> dict:
    """Restore from a backup archive.

    mode="replace": Wipe all existing data and replace with backup.
    mode="merge":   Insert records that don't conflict (skip on PK collision).

    Returns summary dict with counts of restored records.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(tmp, filter="data")

        backup_root = tmp / "backup"
        if not backup_root.is_dir():
            raise ValueError("Invalid backup archive: missing 'backup/' root")

        manifest_path = backup_root / "manifest.json"
        if not manifest_path.exists():
            raise ValueError("Invalid backup archive: missing manifest.json")

        manifest = json.loads(manifest_path.read_text())
        db_dir = backup_root / "database"

        restored_counts = {}

        if mode == "replace":
            # Delete in reverse dependency order
            for table_name, model_cls in reversed(TABLE_EXPORT_ORDER):
                await db.execute(text(f"DELETE FROM {model_cls.__tablename__}"))
            await db.flush()

        for table_name, model_cls in TABLE_EXPORT_ORDER:
            json_file = db_dir / f"{table_name}.json"
            if not json_file.exists():
                restored_counts[table_name] = 0
                continue

            records = json.loads(json_file.read_text())
            count = 0

            for record in records:
                if mode == "merge":
                    pk_col = list(model_cls.__table__.primary_key.columns)[0].name
                    existing = await db.execute(
                        select(model_cls).where(
                            getattr(model_cls, pk_col) == record[pk_col]
                        )
                    )
                    if existing.scalar_one_or_none():
                        continue

                # Convert ISO datetime strings back to datetime objects
                for col in model_cls.__table__.columns:
                    if col.name in record and record[col.name] is not None:
                        if "DateTime" in str(col.type) or "DATETIME" in str(col.type).upper():
                            try:
                                record[col.name] = datetime.fromisoformat(
                                    str(record[col.name])
                                )
                            except (ValueError, TypeError):
                                pass

                obj = model_cls(**record)
                db.add(obj)
                count += 1

            await db.flush()
            restored_counts[table_name] = count

        # Restore dataset files
        backup_datasets = backup_root / "datasets"
        if backup_datasets.is_dir():
            dest = Path(settings.data_dir) / "datasets"
            if mode == "replace" and dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(backup_datasets, dest, dirs_exist_ok=True)

        # Restore project/job files
        backup_projects = backup_root / "projects"
        if backup_projects.is_dir():
            dest = settings.project_dir
            if mode == "replace" and dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(backup_projects, dest, dirs_exist_ok=True)

        # Restore admin defaults
        backup_defaults = backup_root / "admin_defaults.json"
        if backup_defaults.exists():
            shutil.copy2(
                backup_defaults, Path(settings.data_dir) / "admin_defaults.json"
            )

    await db.commit()

    _log.info("Backup restored (%s mode): %s", mode, restored_counts)
    return {
        "status": "restored",
        "mode": mode,
        "manifest": manifest,
        "restored_counts": restored_counts,
    }
