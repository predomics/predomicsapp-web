"""Health check endpoint."""

from fastapi import APIRouter
from ..models.schemas import HealthResponse
from ..services.engine import check_engine
from ..services.scitq_client import is_enabled as scitq_is_enabled
from ..core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check API health and gpredomicspy availability."""
    return HealthResponse(
        status="ok",
        version="0.1.0",
        gpredomicspy_available=check_engine(),
        scitq_enabled=scitq_is_enabled(),
        scitq_server=settings.scitq_server or None,
    )
