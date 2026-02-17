"""Data exploration endpoints — feature statistics and filtering via Rust engine."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.deps import get_current_user, get_project_with_access
from ..models.db_models import User, Project
from ..services import data_analysis
from ..services import msp_annotations
from ..services import coabundance
from ..services import storage

router = APIRouter(prefix="/data-explore", tags=["data-explore"])


def _resolve_train_files(project: Project) -> tuple[str, str, bool]:
    """Find xtrain and ytrain disk paths from project relationships.

    Returns (x_path, y_path, features_in_rows).
    The project must have been loaded with selectinload for dataset_links -> dataset -> files.
    """
    x_path = y_path = None
    for link in project.dataset_links:
        for f in link.dataset.files:
            if f.role == "xtrain":
                x_path = f.disk_path
            elif f.role == "ytrain":
                y_path = f.disk_path
    if not x_path or not y_path:
        raise HTTPException(
            status_code=404,
            detail="X train and/or y train files not found. Upload datasets first.",
        )
    return x_path, y_path


@router.get("/{project_id}/summary")
async def get_data_summary(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get basic data dimensions and class distribution (viewer access)."""
    project, _ = await get_project_with_access(project_id, user, db, require_role="viewer")
    x_path, y_path = _resolve_train_files(project)

    result = data_analysis.run_filtering(x_path, y_path)
    return {
        "n_features": result["n_features"],
        "n_samples": result["n_samples"],
        "n_classes": result["n_classes"],
        "class_labels": result["class_labels"],
        "class_counts": result["class_counts"],
    }


@router.get("/{project_id}/feature-stats")
async def get_feature_stats(
    project_id: str,
    method: str = "wilcoxon",
    prevalence_pct: float = 10.0,
    max_pvalue: float = 0.05,
    min_feature_value: float = 0.0,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get per-feature statistics computed by the Rust filtering engine (viewer access).

    Returns all features with their stats (mean, std, prevalence, significance, class).
    """
    if method not in ("wilcoxon", "studentt", "bayesian_fisher"):
        raise HTTPException(400, f"Invalid method: {method}")

    project, _ = await get_project_with_access(project_id, user, db, require_role="viewer")
    x_path, y_path = _resolve_train_files(project)

    result = data_analysis.run_filtering(
        x_path, y_path,
        method=method,
        prevalence_pct=prevalence_pct,
        max_pvalue=max_pvalue,
        min_feature_value=min_feature_value,
    )
    return {
        "features": result["features"],
        "selected_count": result["selected_count"],
        "method": result["method"],
        "n_features": result["n_features"],
    }


@router.get("/{project_id}/distributions")
async def get_distributions(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get pre-binned histogram data for prevalence and SD distributions (viewer access)."""
    project, _ = await get_project_with_access(project_id, user, db, require_role="viewer")
    x_path, y_path = _resolve_train_files(project)

    result = data_analysis.run_filtering(x_path, y_path)
    distributions = data_analysis.compute_distributions(result["features"])
    distributions["class_distribution"] = result["class_counts"]
    return distributions


@router.get("/{project_id}/feature-abundance")
async def get_feature_abundance(
    project_id: str,
    features: str = "",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get boxplot summary stats per class for selected features (viewer access).

    Pass feature names as comma-separated string, max 100.
    """
    if not features:
        raise HTTPException(400, "No features specified")

    feature_list = [f.strip() for f in features.split(",") if f.strip()][:100]
    if not feature_list:
        raise HTTPException(400, "No valid features specified")

    project, _ = await get_project_with_access(project_id, user, db, require_role="viewer")
    x_path, y_path = _resolve_train_files(project)

    abundance = data_analysis.compute_feature_abundance(
        x_path, y_path, feature_list
    )
    return {"features": abundance}


@router.get("/{project_id}/barcode-data")
async def get_barcode_data(
    project_id: str,
    features: str = "",
    max_samples: int = 500,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get raw feature values per sample for barcode heatmap (viewer access).

    Returns a matrix of shape (n_features, n_samples) with samples ordered by class.
    Pass feature names as comma-separated string, max 100.
    """
    if not features:
        raise HTTPException(400, "No features specified")

    feature_list = [f.strip() for f in features.split(",") if f.strip()][:100]
    if not feature_list:
        raise HTTPException(400, "No valid features specified")

    project, _ = await get_project_with_access(project_id, user, db, require_role="viewer")
    x_path, y_path = _resolve_train_files(project)

    barcode = data_analysis.compute_barcode_data(
        x_path, y_path, feature_list, max_samples=max_samples
    )
    return barcode


@router.get("/{project_id}/pcoa")
async def get_pcoa(
    project_id: str,
    metric: str = "braycurtis",
    features: str = "",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute PCoA with confidence ellipses and PERMANOVA (viewer access).

    Returns 3D coordinates, sample classes, % variance explained per axis,
    95% confidence ellipses per class, and PERMANOVA test results.
    Supported metrics: braycurtis (default), euclidean, jaccard, cosine.
    Pass feature names as comma-separated string to restrict to FBM features.
    """
    allowed_metrics = ("braycurtis", "euclidean", "jaccard", "cosine")
    if metric not in allowed_metrics:
        raise HTTPException(400, f"Invalid metric: {metric}. Choose from {allowed_metrics}")

    project, _ = await get_project_with_access(project_id, user, db, require_role="viewer")
    x_path, y_path = _resolve_train_files(project)

    feature_names = None
    if features:
        feature_names = [f.strip() for f in features.split(",") if f.strip()]

    pcoa_result = data_analysis.compute_pcoa(
        x_path, y_path, metric=metric, feature_names=feature_names,
    )
    return pcoa_result


@router.get("/{project_id}/coabundance-network")
async def get_coabundance_network(
    project_id: str,
    min_prevalence_pct: float = 30.0,
    correlation_threshold: float = 0.3,
    class_filter: str = "all",
    features: str = "",
    job_id: str = "",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute co-abundance ecosystem network from the abundance matrix (viewer access).

    Returns nodes with taxonomy coloring, edges with Spearman correlations,
    Louvain community modules, and optional FBM annotation.
    """
    if class_filter not in ("all", "0", "1"):
        raise HTTPException(400, f"Invalid class_filter: {class_filter}. Choose from all, 0, 1")

    project, _ = await get_project_with_access(project_id, user, db, require_role="viewer")
    x_path, y_path = _resolve_train_files(project)

    feature_names = None
    if features:
        feature_names = [f.strip() for f in features.split(",") if f.strip()]

    job_results = None
    if job_id:
        job_results = storage.get_job_result(project_id, job_id)

    result = coabundance.compute_coabundance_network(
        x_path, y_path,
        min_prevalence_pct=min_prevalence_pct,
        correlation_threshold=correlation_threshold,
        class_filter=class_filter,
        feature_names=feature_names,
        job_results=job_results,
    )
    return result


@router.post("/msp-annotations")
async def get_msp_annotations(
    body: dict,
    user: User = Depends(get_current_user),
):
    """Look up MSP taxonomic annotations for a list of feature names.

    Fetches from biobanks.gmt.bio with local caching.
    Body: {"features": ["msp_0001", "msp_0069", ...]}
    """
    feature_names = body.get("features", [])
    if not feature_names or not isinstance(feature_names, list):
        raise HTTPException(400, "Provide a 'features' list")
    annotations = msp_annotations.get_annotations(feature_names[:2000])
    return {"annotations": annotations}
