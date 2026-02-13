"""Health check endpoint."""

from fastapi import APIRouter
from ..models.schemas import HealthResponse
from ..services.engine import check_engine

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check API health and gpredomicspy availability."""
    return HealthResponse(
        status="ok",
        version="0.1.0",
        gpredomicspy_available=check_engine(),
    )
