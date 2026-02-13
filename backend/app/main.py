"""PredomicsApp FastAPI application."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .core.config import settings
from .routers import health, projects, analysis
from .services.storage import ensure_dirs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown events."""
    ensure_dirs()
    logging.getLogger(__name__).info(
        "PredomicsApp started — data_dir=%s", settings.data_dir
    )
    yield


app = FastAPI(
    title="PredomicsApp API",
    description="Web API for gpredomics — sparse interpretable ML model discovery",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for Vue.js dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router)
app.include_router(projects.router, prefix="/api")
app.include_router(analysis.router, prefix="/api")
