"""Pydantic schemas for API request/response models."""

from __future__ import annotations
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Algorithm(str, Enum):
    ga = "ga"
    beam = "beam"
    mcmc = "mcmc"


class FitFunction(str, Enum):
    auc = "auc"
    specificity = "specificity"
    sensitivity = "sensitivity"
    mcc = "mcc"
    f1_score = "f1_score"
    g_mean = "g_mean"


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


# ---------------------------------------------------------------------------
# Parameter schemas
# ---------------------------------------------------------------------------

class GeneralParams(BaseModel):
    algo: Algorithm = Algorithm.ga
    language: str = "bin,ter,ratio"
    data_type: str = "raw,prev"
    fit: FitFunction = FitFunction.auc
    seed: int = 42
    thread_number: int = 4
    k_penalty: float = 0.0001
    cv: bool = False
    gpu: bool = False


class GaParams(BaseModel):
    population_size: int = 5000
    max_epochs: int = 100
    min_epochs: int = 1
    max_age_best_model: int = 100
    k_min: int = 1
    k_max: int = 200
    select_elite_pct: float = 2.0
    select_niche_pct: float = 20.0
    select_random_pct: float = 10.0
    mutated_children_pct: float = 80.0


class BeamParams(BaseModel):
    k_min: int = 2
    k_max: int = 100
    best_models_criterion: float = 10.0
    max_nb_of_models: int = 20000


class McmcParams(BaseModel):
    n_iter: int = 10000
    n_burn: int = 5000
    lambda_: float = Field(0.001, alias="lambda")
    nmin: int = 10


class DataConfig(BaseModel):
    features_in_rows: bool = True
    inverse_classes: bool = False
    holdout_ratio: float = 0.20
    feature_minimal_prevalence_pct: int = 10
    feature_selection_method: str = "wilcoxon"
    feature_maximal_adj_pvalue: float = 1.0


class CvParams(BaseModel):
    outer_folds: int = 5
    inner_folds: int = 5
    overfit_penalty: float = 0.0


class RunConfig(BaseModel):
    """Full configuration for a gpredomics run."""
    general: GeneralParams = GeneralParams()
    ga: GaParams = GaParams()
    beam: BeamParams = BeamParams()
    mcmc: McmcParams = McmcParams()
    data: DataConfig = DataConfig()
    cv: CvParams = CvParams()


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class IndividualResponse(BaseModel):
    k: int
    auc: float
    fit: float
    accuracy: float
    sensitivity: float
    specificity: float
    threshold: float
    language: str
    data_type: str
    epoch: int
    features: dict[int, int]  # feature_index -> coefficient sign


class PopulationResponse(BaseModel):
    size: int
    individuals: list[IndividualResponse]


class ExperimentSummary(BaseModel):
    job_id: str
    status: JobStatus
    fold_count: int = 0
    generation_count: int = 0
    execution_time: float = 0.0
    feature_count: int = 0
    sample_count: int = 0
    best_auc: Optional[float] = None
    best_k: Optional[int] = None


class ExperimentDetail(ExperimentSummary):
    feature_names: list[str] = []
    sample_names: list[str] = []
    best_individual: Optional[IndividualResponse] = None


class DatasetInfo(BaseModel):
    filename: str
    n_features: int
    n_samples: int
    n_classes: int
    class_labels: list[str] = []
    features_in_rows: bool = True


class DatasetRef(BaseModel):
    id: str
    filename: str
    path: str = ""


class ProjectInfo(BaseModel):
    project_id: str
    name: str
    created_at: str
    datasets: list[DatasetRef] = []
    jobs: list[str] = []


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    gpredomicspy_available: bool = False
