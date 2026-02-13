"""Comprehensive API tests for PredomicsApp backend."""

import os
import shutil
import tempfile
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# Override settings before importing app
_tmp = tempfile.mkdtemp()
os.environ["PREDOMICS_DATA_DIR"] = _tmp
os.environ["PREDOMICS_PROJECT_DIR"] = os.path.join(_tmp, "projects")
os.environ["PREDOMICS_UPLOAD_DIR"] = os.path.join(_tmp, "uploads")
os.environ["PREDOMICS_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["PREDOMICS_SECRET_KEY"] = "test-secret-key"

from app.main import app  # noqa: E402
from app.core.database import engine, Base, get_db, async_session_factory  # noqa: E402
from app.services import engine as ml_engine  # noqa: E402


@pytest_asyncio.fixture
async def db_session():
    """Create tables and yield a test database session."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session_factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(db_session):
    """HTTP client with overridden DB dependency."""
    async def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_client(client):
    """Authenticated HTTP client with a pre-registered user."""
    await client.post("/api/auth/register", json={
        "email": "test@example.com",
        "password": "testpass123",
        "full_name": "Test User",
    })
    resp = await client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "testpass123",
    })
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest.fixture(autouse=True)
def clean_data():
    """Clean data directory between tests."""
    yield
    data_dir = os.environ["PREDOMICS_DATA_DIR"]
    for d in ["projects", "uploads"]:
        p = os.path.join(data_dir, d)
        if os.path.exists(p):
            shutil.rmtree(p)
            os.makedirs(p)


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

class TestHealth:
    @pytest.mark.asyncio
    async def test_health_returns_ok(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_health_has_correct_fields(self, client):
        resp = await client.get("/health")
        data = resp.json()
        assert "status" in data
        assert "version" in data
        assert "gpredomicspy_available" in data


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

class TestAuth:
    @pytest.mark.asyncio
    async def test_register_new_user(self, client):
        resp = await client.post("/api/auth/register", json={
            "email": "new@example.com", "password": "pass123"
        })
        assert resp.status_code == 201
        assert resp.json()["email"] == "new@example.com"

    @pytest.mark.asyncio
    async def test_register_duplicate_email_returns_409(self, client):
        await client.post("/api/auth/register", json={"email": "dup@x.com", "password": "p"})
        resp = await client.post("/api/auth/register", json={"email": "dup@x.com", "password": "p"})
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_login_returns_token(self, client):
        await client.post("/api/auth/register", json={"email": "a@b.com", "password": "p"})
        resp = await client.post("/api/auth/login", json={"email": "a@b.com", "password": "p"})
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    @pytest.mark.asyncio
    async def test_login_wrong_password_returns_401(self, client):
        await client.post("/api/auth/register", json={"email": "a@b.com", "password": "right"})
        resp = await client.post("/api/auth/login", json={"email": "a@b.com", "password": "wrong"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_me_without_token_returns_401(self, client):
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_me_with_valid_token(self, auth_client):
        resp = await auth_client.get("/api/auth/me")
        assert resp.status_code == 200
        assert resp.json()["email"] == "test@example.com"


# ---------------------------------------------------------------------------
# Projects (all require auth)
# ---------------------------------------------------------------------------

class TestProjects:
    @pytest.mark.asyncio
    async def test_create_project(self, auth_client):
        resp = await auth_client.post("/api/projects/", params={"name": "TestProject"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "TestProject"
        assert "project_id" in data

    @pytest.mark.asyncio
    async def test_list_projects_empty(self, auth_client):
        resp = await auth_client.get("/api/projects/")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_list_projects_after_create(self, auth_client):
        await auth_client.post("/api/projects/", params={"name": "P1"})
        resp = await auth_client.get("/api/projects/")
        assert len(resp.json()) == 1
        assert resp.json()[0]["name"] == "P1"

    @pytest.mark.asyncio
    async def test_get_project_by_id(self, auth_client):
        create_resp = await auth_client.post("/api/projects/", params={"name": "Mine"})
        pid = create_resp.json()["project_id"]
        resp = await auth_client.get(f"/api/projects/{pid}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Mine"

    @pytest.mark.asyncio
    async def test_get_nonexistent_project_returns_404(self, auth_client):
        resp = await auth_client.get("/api/projects/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_project(self, auth_client):
        create_resp = await auth_client.post("/api/projects/", params={"name": "Del"})
        pid = create_resp.json()["project_id"]
        resp = await auth_client.delete(f"/api/projects/{pid}")
        assert resp.status_code == 200

        resp = await auth_client.get(f"/api/projects/{pid}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_project_returns_404(self, auth_client):
        resp = await auth_client.delete("/api/projects/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_project_has_created_at_timestamp(self, auth_client):
        resp = await auth_client.post("/api/projects/", params={"name": "TimedProject"})
        data = resp.json()
        assert "created_at" in data
        assert "T" in data["created_at"]  # ISO format

    @pytest.mark.asyncio
    async def test_unauthenticated_access_returns_401(self, client):
        resp = await client.get("/api/projects/")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------

class TestDatasets:
    @pytest.mark.asyncio
    async def test_upload_tsv_dataset(self, auth_client):
        create_resp = await auth_client.post("/api/projects/", params={"name": "ds_test"})
        pid = create_resp.json()["project_id"]
        resp = await auth_client.post(
            f"/api/projects/{pid}/datasets",
            files={"file": ("X.tsv", b"id\ts1\ts2\nf1\t0.1\t0.2\n", "text/plain")},
        )
        assert resp.status_code == 200
        assert resp.json()["filename"] == "X.tsv"

    @pytest.mark.asyncio
    async def test_upload_csv_dataset(self, auth_client):
        create_resp = await auth_client.post("/api/projects/", params={"name": "csv_test"})
        pid = create_resp.json()["project_id"]
        resp = await auth_client.post(
            f"/api/projects/{pid}/datasets",
            files={"file": ("data.csv", b"id,s1,s2\nf1,0.1,0.2\n", "text/plain")},
        )
        assert resp.status_code == 200
        assert resp.json()["filename"] == "data.csv"

    @pytest.mark.asyncio
    async def test_upload_to_nonexistent_project_returns_404(self, auth_client):
        resp = await auth_client.post(
            "/api/projects/nonexistent/datasets",
            files={"file": ("X.tsv", b"id\ts1\nf1\t0.1\n", "text/plain")},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_upload_updates_project_metadata(self, auth_client):
        create_resp = await auth_client.post("/api/projects/", params={"name": "meta_test"})
        pid = create_resp.json()["project_id"]
        await auth_client.post(
            f"/api/projects/{pid}/datasets",
            files={"file": ("X.tsv", b"id\ts1\nf1\t0.1\n", "text/plain")},
        )
        resp = await auth_client.get(f"/api/projects/{pid}")
        datasets = resp.json()["datasets"]
        assert len(datasets) == 1
        assert datasets[0]["filename"] == "X.tsv"


# ---------------------------------------------------------------------------
# Analysis endpoints
# ---------------------------------------------------------------------------

class TestAnalysis:
    @pytest.mark.asyncio
    async def test_run_analysis_returns_job_id(self, auth_client):
        create_resp = await auth_client.post("/api/projects/", params={"name": "run_test"})
        pid = create_resp.json()["project_id"]

        await auth_client.post(
            f"/api/projects/{pid}/datasets",
            files={"file": ("X.tsv", b"id\ts1\ts2\nf1\t0.1\t0.2\n", "text/plain")},
        )
        await auth_client.post(
            f"/api/projects/{pid}/datasets",
            files={"file": ("y.tsv", b"id\tclass\ns1\t0\ns2\t1\n", "text/plain")},
        )

        proj = (await auth_client.get(f"/api/projects/{pid}")).json()
        datasets = proj["datasets"]
        x_id = datasets[0]["id"]
        y_id = datasets[1]["id"]

        config = {
            "general": {"algo": "ga", "language": "bin", "data_type": "raw", "fit": "auc",
                        "seed": 42, "thread_number": 1, "k_penalty": 0.0001, "cv": False, "gpu": False},
            "ga": {"population_size": 50, "max_epochs": 2, "k_min": 1, "k_max": 10},
        }

        with patch("app.services.engine.run_experiment", return_value=ml_engine._mock_results()):
            resp = await auth_client.post(
                f"/api/analysis/{pid}/run",
                json=config,
                params={"x_dataset_id": x_id, "y_dataset_id": y_id},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "job_id" in data
        assert data["status"] in ["pending", "running"]

    @pytest.mark.asyncio
    async def test_get_job_status_nonexistent_returns_404(self, auth_client):
        create_resp = await auth_client.post("/api/projects/", params={"name": "status_test"})
        pid = create_resp.json()["project_id"]
        resp = await auth_client.get(f"/api/analysis/{pid}/jobs/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_jobs_empty(self, auth_client):
        create_resp = await auth_client.post("/api/projects/", params={"name": "jobs_test"})
        pid = create_resp.json()["project_id"]
        resp = await auth_client.get(f"/api/analysis/{pid}/jobs")
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

class TestSchemaValidation:
    @pytest.mark.asyncio
    async def test_run_with_invalid_algo_returns_422(self, auth_client):
        create_resp = await auth_client.post("/api/projects/", params={"name": "val_test"})
        pid = create_resp.json()["project_id"]

        config = {"general": {"algo": "invalid_algo"}}
        resp = await auth_client.post(
            f"/api/analysis/{pid}/run",
            json=config,
            params={"x_dataset_id": "abc", "y_dataset_id": "def"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_run_with_invalid_fit_returns_422(self, auth_client):
        create_resp = await auth_client.post("/api/projects/", params={"name": "fit_test"})
        pid = create_resp.json()["project_id"]

        config = {"general": {"fit": "invalid_fit"}}
        resp = await auth_client.post(
            f"/api/analysis/{pid}/run",
            json=config,
            params={"x_dataset_id": "abc", "y_dataset_id": "def"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_run_with_defaults_accepts_empty_config(self, auth_client):
        """RunConfig should have sensible defaults for all fields."""
        create_resp = await auth_client.post("/api/projects/", params={"name": "default_test"})
        pid = create_resp.json()["project_id"]

        await auth_client.post(
            f"/api/projects/{pid}/datasets",
            files={"file": ("X.tsv", b"id\ts1\nf1\t0.1\n", "text/plain")},
        )
        await auth_client.post(
            f"/api/projects/{pid}/datasets",
            files={"file": ("y.tsv", b"id\tc\ns1\t0\n", "text/plain")},
        )

        proj = (await auth_client.get(f"/api/projects/{pid}")).json()
        ds = proj["datasets"]
        x_id = ds[0]["id"]
        y_id = ds[1]["id"]

        with patch("app.services.engine.run_experiment", return_value=ml_engine._mock_results()):
            resp = await auth_client.post(
                f"/api/analysis/{pid}/run",
                json={},
                params={"x_dataset_id": x_id, "y_dataset_id": y_id},
            )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Project isolation between users
# ---------------------------------------------------------------------------

class TestProjectIsolation:
    @pytest.mark.asyncio
    async def test_user_cannot_see_other_users_projects(self, client):
        # Register two users
        await client.post("/api/auth/register", json={"email": "a@x.com", "password": "p"})
        await client.post("/api/auth/register", json={"email": "b@x.com", "password": "p"})

        # User A creates a project
        r = await client.post("/api/auth/login", json={"email": "a@x.com", "password": "p"})
        token_a = r.json()["access_token"]
        await client.post("/api/projects/", params={"name": "a_proj"},
                          headers={"Authorization": f"Bearer {token_a}"})

        # User B should not see it
        r = await client.post("/api/auth/login", json={"email": "b@x.com", "password": "p"})
        token_b = r.json()["access_token"]
        resp = await client.get("/api/projects/",
                                headers={"Authorization": f"Bearer {token_b}"})
        assert resp.json() == []
