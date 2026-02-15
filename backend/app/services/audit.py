"""Audit logging service."""

from __future__ import annotations

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.db_models import AuditLog, User

_log = logging.getLogger(__name__)

# Action constants
ACTION_LOGIN = "login"
ACTION_REGISTER = "register"
ACTION_JOB_LAUNCH = "job.launch"
ACTION_JOB_DELETE = "job.delete"
ACTION_DATASET_UPLOAD = "dataset.upload"
ACTION_DATASET_DELETE = "dataset.delete"
ACTION_PROJECT_CREATE = "project.create"
ACTION_PROJECT_DELETE = "project.delete"
ACTION_SHARE_CREATE = "share.create"
ACTION_SHARE_REVOKE = "share.revoke"
ACTION_BACKUP_CREATE = "backup.create"
ACTION_BACKUP_RESTORE = "backup.restore"
ACTION_ADMIN_USER_UPDATE = "admin.user.update"
ACTION_ADMIN_USER_DELETE = "admin.user.delete"


async def log_action(
    db: AsyncSession,
    user: User | None,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
):
    """Record an audit event. Non-blocking — swallows errors."""
    try:
        entry = AuditLog(
            user_id=user.id if user else None,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
        )
        db.add(entry)
        await db.flush()
    except Exception as e:
        _log.warning("Audit log failed: %s", e)
