"""Basic API tests."""

import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_create_and_list_projects(client):
    # Create
    resp = await client.post("/api/projects/", params={"name": "test_project"})
    assert resp.status_code == 200
    project = resp.json()
    assert project["name"] == "test_project"
    pid = project["project_id"]

    # List
    resp = await client.get("/api/projects/")
    assert resp.status_code == 200
    projects = resp.json()
    assert any(p["project_id"] == pid for p in projects)

    # Get
    resp = await client.get(f"/api/projects/{pid}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "test_project"

    # Delete
    resp = await client.delete(f"/api/projects/{pid}")
    assert resp.status_code == 200
