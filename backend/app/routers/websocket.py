"""WebSocket endpoint for live job log streaming."""

import asyncio
import json
import logging
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select

from ..core.config import settings
from ..core.database import async_session_factory
from ..core.security import decode_access_token
from ..models.db_models import User, Job, Project, ProjectShare

_log = logging.getLogger(__name__)
router = APIRouter()


async def _verify_ws_access(token: str, project_id: str) -> bool:
    """Verify the WebSocket token grants access to the project."""
    user_id = decode_access_token(token)
    if not user_id:
        return False
    async with async_session_factory() as db:
        result = await db.execute(
            select(User).where(User.id == user_id, User.is_active.is_(True))
        )
        user = result.scalar_one_or_none()
        if not user:
            return False
        # Check project ownership
        result = await db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        if not project:
            return False
        if project.user_id == user_id:
            return True
        # Check shared access
        result = await db.execute(
            select(ProjectShare).where(
                ProjectShare.project_id == project_id,
                ProjectShare.user_id == user_id,
            )
        )
        return result.scalar_one_or_none() is not None


@router.websocket("/ws/jobs/{project_id}/{job_id}")
async def job_log_ws(
    websocket: WebSocket,
    project_id: str,
    job_id: str,
    token: str = Query(...),
):
    """Stream job console.log in real-time (tail -f style).

    The client passes the JWT token as a query parameter since
    WebSocket does not support Authorization headers in browsers.

    Messages sent to client:
    - {"type": "status", "status": "running"}
    - {"type": "log", "content": "...new lines..."}
    - {"type": "done", "status": "completed"|"failed"}
    - {"type": "error", "message": "..."}
    """
    if not await _verify_ws_access(token, project_id):
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()

    job_dir = Path(settings.project_dir) / project_id / "jobs" / job_id
    log_path = job_dir / "console.log"
    progress_path = job_dir / "progress.json"
    last_size = 0
    last_status = None
    last_progress_size = 0

    try:
        while True:
            # Check job status from DB
            async with async_session_factory() as db:
                result = await db.execute(
                    select(Job).where(Job.id == job_id, Job.project_id == project_id)
                )
                job = result.scalar_one_or_none()
                if not job:
                    await websocket.send_json({"type": "error", "message": "Job not found"})
                    break

                current_status = job.status

            # Send status change
            if current_status != last_status:
                await websocket.send_json({
                    "type": "status",
                    "status": current_status,
                })
                last_status = current_status

            # Stream new log content
            if log_path.exists():
                current_size = log_path.stat().st_size
                if current_size > last_size:
                    with open(log_path, "r") as f:
                        f.seek(last_size)
                        new_content = f.read()
                    if new_content:
                        await websocket.send_json({
                            "type": "log",
                            "content": new_content,
                        })
                    last_size = current_size

            # Stream structured progress metrics
            if progress_path.exists():
                try:
                    p_size = progress_path.stat().st_size
                    if p_size != last_progress_size:
                        progress_data = json.loads(progress_path.read_text())
                        await websocket.send_json({
                            "type": "progress",
                            "data": progress_data,
                        })
                        last_progress_size = p_size
                except Exception:
                    pass

            # Stop on terminal state
            if current_status in ("completed", "failed"):
                await websocket.send_json({
                    "type": "done",
                    "status": current_status,
                })
                break

            await asyncio.sleep(0.5)

    except WebSocketDisconnect:
        _log.debug("WebSocket client disconnected for job %s", job_id)
    except Exception as e:
        _log.error("WebSocket error for job %s: %s", job_id, e)
        try:
            await websocket.close(code=1011, reason=str(e))
        except Exception:
            pass
