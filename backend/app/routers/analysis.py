"""Analysis execution endpoints — run gpredomics and retrieve results."""

from __future__ import annotations
import logging
import uuid
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException, BackgroundTasks

from ..models.schemas import (
    RunConfig,
    ExperimentSummary,
    ExperimentDetail,
    IndividualResponse,
    JobStatus,
)
from ..services import engine, storage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["analysis"])

# In-memory job status tracker (replace with DB/Redis for production)
_jobs: dict[str, dict] = {}


@router.post("/{project_id}/run", response_model=ExperimentSummary)
async def run_analysis(
    project_id: str,
    config: RunConfig,
    x_dataset_id: str,
    y_dataset_id: str,
    xtest_dataset_id: str = "",
    ytest_dataset_id: str = "",
    background_tasks: BackgroundTasks = None,
):
    """Launch a gpredomics analysis run.

    The analysis runs in the background. Poll the status endpoint to check progress.
    """
    meta = storage.get_project(project_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Project not found")

    # Resolve dataset paths
    x_path = storage.get_dataset_path(project_id, x_dataset_id)
    y_path = storage.get_dataset_path(project_id, y_dataset_id)
    if not x_path or not y_path:
        raise HTTPException(status_code=404, detail="Dataset not found")

    xtest_path = ""
    ytest_path = ""
    if xtest_dataset_id:
        p = storage.get_dataset_path(project_id, xtest_dataset_id)
        xtest_path = str(p) if p else ""
    if ytest_dataset_id:
        p = storage.get_dataset_path(project_id, ytest_dataset_id)
        ytest_path = str(p) if p else ""

    # Create job
    job_id = uuid.uuid4().hex[:12]
    job_dir = Path(storage.settings.project_dir) / project_id / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    _jobs[job_id] = {
        "project_id": project_id,
        "status": JobStatus.pending,
        "results": None,
    }

    # Write param.yaml
    config_dict = config.model_dump()
    param_path = engine.write_param_yaml(
        config=config_dict,
        x_path=str(x_path),
        y_path=str(y_path),
        xtest_path=xtest_path,
        ytest_path=ytest_path,
        output_dir=str(job_dir),
    )

    # Run in background thread (gpredomics is CPU-bound)
    background_tasks.add_task(_run_job, job_id, project_id, param_path)

    return ExperimentSummary(job_id=job_id, status=JobStatus.pending)


def _run_job(job_id: str, project_id: str, param_path: str) -> None:
    """Execute gpredomics in a background thread."""
    _jobs[job_id]["status"] = JobStatus.running
    try:
        results = engine.run_experiment(param_path)
        _jobs[job_id]["status"] = JobStatus.completed
        _jobs[job_id]["results"] = results
        storage.save_job_result(project_id, job_id, results)
        logger.info("Job %s completed: AUC=%.4f", job_id, results["best_individual"]["auc"])
    except Exception as e:
        _jobs[job_id]["status"] = JobStatus.failed
        _jobs[job_id]["error"] = str(e)
        logger.error("Job %s failed: %s", job_id, e)


@router.get("/{project_id}/jobs/{job_id}", response_model=ExperimentSummary)
async def get_job_status(project_id: str, job_id: str):
    """Get the status of a running or completed job."""
    job = _jobs.get(job_id)
    if not job:
        # Try loading from disk
        results = storage.get_job_result(project_id, job_id)
        if results:
            return _results_to_summary(job_id, JobStatus.completed, results)
        raise HTTPException(status_code=404, detail="Job not found")

    if job["results"]:
        return _results_to_summary(job_id, job["status"], job["results"])

    return ExperimentSummary(job_id=job_id, status=job["status"])


@router.get("/{project_id}/jobs/{job_id}/detail", response_model=ExperimentDetail)
async def get_job_detail(project_id: str, job_id: str):
    """Get detailed results of a completed job."""
    results = _jobs.get(job_id, {}).get("results")
    if not results:
        results = storage.get_job_result(project_id, job_id)
    if not results:
        raise HTTPException(status_code=404, detail="Job not found or not completed")

    best = results.get("best_individual", {})
    return ExperimentDetail(
        job_id=job_id,
        status=JobStatus.completed,
        fold_count=results.get("fold_count", 0),
        generation_count=results.get("generation_count", 0),
        execution_time=results.get("execution_time", 0),
        feature_count=len(results.get("feature_names", [])),
        sample_count=len(results.get("sample_names", [])),
        best_auc=best.get("auc"),
        best_k=best.get("k"),
        feature_names=results.get("feature_names", []),
        sample_names=results.get("sample_names", []),
        best_individual=IndividualResponse(**best) if best else None,
    )


@router.get("/{project_id}/jobs")
async def list_jobs(project_id: str):
    """List all jobs for a project."""
    jobs = []
    for jid, job in _jobs.items():
        if job["project_id"] == project_id:
            if job["results"]:
                jobs.append(_results_to_summary(jid, job["status"], job["results"]))
            else:
                jobs.append(ExperimentSummary(job_id=jid, status=job["status"]))
    return jobs


def _results_to_summary(job_id: str, status: JobStatus, results: dict) -> ExperimentSummary:
    best = results.get("best_individual", {})
    return ExperimentSummary(
        job_id=job_id,
        status=status,
        fold_count=results.get("fold_count", 0),
        generation_count=results.get("generation_count", 0),
        execution_time=results.get("execution_time", 0),
        feature_count=len(results.get("feature_names", [])),
        sample_count=len(results.get("sample_names", [])),
        best_auc=best.get("auc"),
        best_k=best.get("k"),
    )
