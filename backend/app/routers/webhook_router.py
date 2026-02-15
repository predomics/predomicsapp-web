"""Webhook management endpoints."""

import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.deps import get_current_user
from ..models.db_models import User, Webhook
from ..services.webhooks import send_webhook_sync

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class WebhookCreate(BaseModel):
    name: str
    url: str
    events: list[str] = ["job.completed", "job.failed"]


@router.post("/")
async def create_webhook(
    body: WebhookCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    secret = secrets.token_hex(32)
    wh = Webhook(
        user_id=user.id,
        name=body.name,
        url=body.url,
        events=body.events,
        secret=secret,
    )
    db.add(wh)
    await db.flush()
    return {
        "id": wh.id,
        "name": wh.name,
        "url": wh.url,
        "events": wh.events,
        "secret": secret,
        "created_at": wh.created_at.isoformat(),
    }


@router.get("/")
async def list_webhooks(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Webhook)
        .where(Webhook.user_id == user.id)
        .order_by(Webhook.created_at.desc())
    )
    return [
        {
            "id": w.id,
            "name": w.name,
            "url": w.url,
            "events": w.events,
            "is_active": w.is_active,
            "created_at": w.created_at.isoformat(),
        }
        for w in result.scalars().all()
    ]


@router.delete("/{webhook_id}")
async def delete_webhook(
    webhook_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Webhook).where(Webhook.id == webhook_id, Webhook.user_id == user.id)
    )
    wh = result.scalar_one_or_none()
    if not wh:
        raise HTTPException(status_code=404, detail="Webhook not found")
    await db.delete(wh)
    return {"status": "deleted"}


@router.post("/{webhook_id}/test")
async def test_webhook(
    webhook_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Webhook).where(Webhook.id == webhook_id, Webhook.user_id == user.id)
    )
    wh = result.scalar_one_or_none()
    if not wh:
        raise HTTPException(status_code=404, detail="Webhook not found")

    payload = {"event": "test", "message": "This is a test webhook from PredomicsApp"}
    success = send_webhook_sync(wh.url, payload, wh.secret, retries=1)
    return {"status": "delivered" if success else "failed"}
