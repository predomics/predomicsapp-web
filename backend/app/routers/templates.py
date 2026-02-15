"""Project template endpoints — admin CRUD + public list."""

import json
import secrets
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..core.config import settings
from ..core.deps import get_admin_user
from ..models.db_models import User

TEMPLATES_PATH = Path(settings.data_dir) / "templates.json"

router = APIRouter(prefix="/admin/templates", tags=["admin"])


class TemplateCreate(BaseModel):
    name: str
    description: str = ""
    category: str = "general"
    params: dict


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    params: Optional[dict] = None


def _load_templates() -> list[dict]:
    if TEMPLATES_PATH.exists():
        return json.loads(TEMPLATES_PATH.read_text())
    return []


def _save_templates(templates: list[dict]) -> None:
    TEMPLATES_PATH.parent.mkdir(parents=True, exist_ok=True)
    TEMPLATES_PATH.write_text(json.dumps(templates, indent=2))


@router.get("/")
async def list_templates(admin: User = Depends(get_admin_user)):
    return _load_templates()


@router.get("/public")
async def list_templates_public():
    """No auth required — used by ParametersTab to populate dropdown."""
    return _load_templates()


@router.post("/")
async def create_template(
    body: TemplateCreate,
    admin: User = Depends(get_admin_user),
):
    templates = _load_templates()
    template = {
        "id": secrets.token_hex(6),
        "name": body.name,
        "description": body.description,
        "category": body.category,
        "params": body.params,
    }
    templates.append(template)
    _save_templates(templates)
    return template


@router.put("/{template_id}")
async def update_template(
    template_id: str,
    body: TemplateUpdate,
    admin: User = Depends(get_admin_user),
):
    templates = _load_templates()
    for t in templates:
        if t["id"] == template_id:
            if body.name is not None:
                t["name"] = body.name
            if body.description is not None:
                t["description"] = body.description
            if body.category is not None:
                t["category"] = body.category
            if body.params is not None:
                t["params"] = body.params
            _save_templates(templates)
            return t
    raise HTTPException(status_code=404, detail="Template not found")


@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    admin: User = Depends(get_admin_user),
):
    templates = _load_templates()
    filtered = [t for t in templates if t["id"] != template_id]
    if len(filtered) == len(templates):
        raise HTTPException(status_code=404, detail="Template not found")
    _save_templates(filtered)
    return {"status": "deleted"}
