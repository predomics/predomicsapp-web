"""Admin endpoints: user management, default configuration, backup/restore."""

import json
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.database import get_db
from ..core.deps import get_admin_user
from ..models.db_models import User, Project, Dataset
from ..models.auth_schemas import AdminUserResponse, AdminUserUpdate

DEFAULTS_PATH = Path(settings.data_dir) / "admin_defaults.json"

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[AdminUserResponse])
async def list_users(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """List all users with project/dataset counts (admin only)."""
    proj_count = (
        select(Project.user_id, func.count(Project.id).label("project_count"))
        .group_by(Project.user_id)
        .subquery()
    )
    ds_count = (
        select(Dataset.user_id, func.count(Dataset.id).label("dataset_count"))
        .group_by(Dataset.user_id)
        .subquery()
    )

    stmt = (
        select(
            User,
            func.coalesce(proj_count.c.project_count, 0).label("project_count"),
            func.coalesce(ds_count.c.dataset_count, 0).label("dataset_count"),
        )
        .outerjoin(proj_count, User.id == proj_count.c.user_id)
        .outerjoin(ds_count, User.id == ds_count.c.user_id)
        .order_by(User.created_at)
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        AdminUserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            is_admin=user.is_admin,
            created_at=user.created_at,
            project_count=pc,
            dataset_count=dc,
        )
        for user, pc, dc in rows
    ]


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
async def update_user(
    user_id: str,
    body: AdminUserUpdate,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle is_active or is_admin flags for a user (admin only)."""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot modify your own admin status")

    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if body.is_active is not None:
        target.is_active = body.is_active
    if body.is_admin is not None:
        target.is_admin = body.is_admin

    pc = await db.execute(
        select(func.count(Project.id)).where(Project.user_id == user_id)
    )
    dc = await db.execute(
        select(func.count(Dataset.id)).where(Dataset.user_id == user_id)
    )

    return AdminUserResponse(
        id=target.id,
        email=target.email,
        full_name=target.full_name,
        is_active=target.is_active,
        is_admin=target.is_admin,
        created_at=target.created_at,
        project_count=pc.scalar() or 0,
        dataset_count=dc.scalar() or 0,
    )


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a user and all their data (admin only). Cascades to projects/datasets."""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    await db.delete(target)
    return {"status": "deleted", "email": target.email}


def _load_defaults() -> dict:
    """Load admin defaults from disk."""
    if DEFAULTS_PATH.exists():
        return json.loads(DEFAULTS_PATH.read_text())
    return {}


def _save_defaults(data: dict) -> None:
    """Save admin defaults to disk."""
    DEFAULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEFAULTS_PATH.write_text(json.dumps(data, indent=2))


@router.get("/defaults")
async def get_defaults(admin: User = Depends(get_admin_user)):
    """Get the admin default parameter overrides (admin only)."""
    return _load_defaults()


@router.get("/defaults/public")
async def get_defaults_public():
    """Get the admin default parameter overrides (public, no auth required).

    Used by the Parameters form to show current server defaults.
    """
    return _load_defaults()


@router.put("/defaults")
async def set_defaults(body: dict, admin: User = Depends(get_admin_user)):
    """Set admin default parameter overrides (admin only).

    Accepts a flat dict of section.key overrides, e.g.:
    {"general.language": "bin,ter", "ga.population_size": 3000, "voting.vote": true}
    """
    _save_defaults(body)
    return body


# ---------------------------------------------------------------------------
# Backup & Restore
# ---------------------------------------------------------------------------

from ..services import backup as backup_service  # noqa: E402


@router.post("/backup")
async def create_backup(
    description: str = "",
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a full system backup (admin only). Returns backup metadata."""
    try:
        result = await backup_service.create_backup(db, description)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backup failed: {e}")


@router.get("/backup/list")
async def list_backups(admin: User = Depends(get_admin_user)):
    """List all available backups (admin only)."""
    return backup_service.list_backups()


@router.get("/backup/download/{backup_id}")
async def download_backup(
    backup_id: str,
    admin: User = Depends(get_admin_user),
):
    """Download a backup archive (admin only)."""
    path = backup_service.get_backup_path(backup_id)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="Backup not found")
    return FileResponse(
        path,
        media_type="application/gzip",
        filename=path.name,
    )


@router.delete("/backup/{backup_id}")
async def delete_backup_endpoint(
    backup_id: str,
    admin: User = Depends(get_admin_user),
):
    """Delete a backup archive (admin only)."""
    if not backup_service.delete_backup(backup_id):
        raise HTTPException(status_code=404, detail="Backup not found")
    return {"status": "deleted", "backup_id": backup_id}


@router.post("/restore")
async def restore_backup(
    file: UploadFile = File(...),
    mode: str = Query("replace", pattern="^(replace|merge)$"),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload and restore from a backup archive (admin only).

    mode: "replace" (wipe and replace) or "merge" (skip conflicts).
    """
    if not file.filename.endswith((".tar.gz", ".tgz")):
        raise HTTPException(status_code=400, detail="Expected a .tar.gz archive")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        result = await backup_service.restore_backup(tmp_path, db, mode=mode)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Restore failed: {e}")
    finally:
        tmp_path.unlink(missing_ok=True)
