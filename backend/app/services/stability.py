"""Model stability analysis service.

Computes stability indices for the Family of Best Models (FBM) population,
inspired by the Shasha Cui internship (Ecole Polytechnique / ICAN, 2017).

Provides:
- Stability indices per sparsity level (Kuncheva, Tanimoto, CW_rel)
- Hierarchical clustering of models (Tanimoto distance)
- Feature prevalence heatmap across sparsity levels
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Stability indices (Drotar & Smekal, Cui 2017)
# ---------------------------------------------------------------------------

def _kuncheva_index(s_i: set, s_j: set, total_features: int) -> float:
    """Kuncheva index: chance-corrected intersection of two feature sets.

    κ(S) = (|S_i ∩ S_j| - d²/c) / (d(1 - d/c))
    where d = |S_i| = |S_j|, c = total number of features.
    """
    d = len(s_i)
    if d == 0:
        return 0.0
    c = total_features
    if c == 0 or d >= c:
        return 0.0
    intersection = len(s_i & s_j)
    numerator = intersection - (d * d / c)
    denominator = d * (1 - d / c)
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _tanimoto_similarity(s_i: set, s_j: set) -> float:
    """Kalousis / Tanimoto similarity: |S_i ∩ S_j| / |S_i ∪ S_j|."""
    if not s_i and not s_j:
        return 1.0
    union = len(s_i | s_j)
    if union == 0:
        return 0.0
    return len(s_i & s_j) / union


def _weighted_consistency(feature_sets: list[set], total_features: int) -> float:
    """Weighted consistency CW: frequency-weighted feature stability.

    CW(S) = Σ_{f ∈ F} (N_f / N) * (N_f - 1) / (K - 1)
    where N_f = # of sets containing feature f, N = total features in union,
    K = # of feature sets.
    """
    k = len(feature_sets)
    if k <= 1:
        return 1.0
    # Count occurrences of each feature
    freq: dict[Any, int] = {}
    for s in feature_sets:
        for f in s:
            freq[f] = freq.get(f, 0) + 1
    n = sum(freq.values())
    if n == 0:
        return 0.0
    cw = sum((nf / n) * ((nf - 1) / (k - 1)) for nf in freq.values())
    return cw


def _relative_weighted_consistency(
    feature_sets: list[set], total_features: int
) -> float:
    """Relative weighted consistency CW_rel: normalized CW.

    CW_rel = (CW - CW_min) / (CW_max - CW_min)
    CW_min ≈ 0 for large feature spaces
    CW_max = 1 when all sets are identical.
    """
    cw = _weighted_consistency(feature_sets, total_features)
    # CW_min for random selection is approximately d/c
    if not feature_sets:
        return 0.0
    d = np.mean([len(s) for s in feature_sets])
    c = total_features
    cw_min = d / c if c > 0 else 0.0
    cw_max = 1.0
    denom = cw_max - cw_min
    if denom <= 0:
        return 0.0
    return max(0.0, min(1.0, (cw - cw_min) / denom))


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def compute_stability_analysis(
    population: list[dict],
    feature_names: list[str],
) -> dict:
    """Compute stability analysis for a model population.

    Parameters
    ----------
    population : list[dict]
        List of model dicts from results JSON. Each has 'metrics' (with 'k',
        'auc', 'accuracy', etc.) and 'features' (dict of idx->coef) or
        'named_features' (dict of name->coef).
    feature_names : list[str]
        Full list of feature names.

    Returns
    -------
    dict with keys:
        stability_by_k : list of {k, n_models, kuncheva, tanimoto, cw_rel,
                                   mean_auc, mean_accuracy}
        dendrogram : {labels, merge_matrix, distances, clusters, n_clusters}
        feature_sparsity_heatmap : {features, sparsity_levels, values}
        model_distance_matrix : {labels, distances}
        stats : {n_models, n_features, k_range, peak_stability_k}
    """
    if not population or not feature_names:
        return _empty_result()

    total_features = len(feature_names)

    # Extract feature sets per model
    models = []
    for i, ind in enumerate(population):
        metrics = ind.get("metrics", {})
        features = ind.get("features", {})
        named = ind.get("named_features", {})
        # Build feature set using indices or names
        if named:
            feat_set = set(named.keys())
        elif features:
            feat_set = set()
            for idx_str in features:
                idx = int(idx_str)
                if 0 <= idx < len(feature_names):
                    feat_set.add(feature_names[idx])
        else:
            feat_set = set()
        models.append({
            "index": i,
            "k": metrics.get("k", len(feat_set)),
            "auc": metrics.get("auc", 0.0),
            "accuracy": metrics.get("accuracy", 0.0),
            "features": feat_set,
            "label": f"M{i}_k{metrics.get('k', len(feat_set))}",
        })

    # --- 1. Stability by sparsity level (k) ---
    stability_by_k = _compute_stability_by_k(models, total_features)

    # --- 2. Hierarchical clustering ---
    dendrogram_data = _compute_dendrogram(models)

    # --- 3. Feature × sparsity heatmap ---
    heatmap = _compute_feature_sparsity_heatmap(models, feature_names)

    # --- 4. Model pairwise distance matrix ---
    distance_matrix = _compute_distance_matrix(models)

    # Stats
    k_values = [m["k"] for m in models]
    peak_k = 0
    if stability_by_k:
        best_entry = max(stability_by_k, key=lambda x: x["tanimoto"])
        peak_k = best_entry["k"]

    return {
        "stability_by_k": stability_by_k,
        "dendrogram": dendrogram_data,
        "feature_sparsity_heatmap": heatmap,
        "model_distance_matrix": distance_matrix,
        "stats": {
            "n_models": len(models),
            "n_features": total_features,
            "k_min": min(k_values) if k_values else 0,
            "k_max": max(k_values) if k_values else 0,
            "peak_stability_k": peak_k,
        },
    }


def _compute_stability_by_k(
    models: list[dict], total_features: int
) -> list[dict]:
    """Compute stability indices grouped by sparsity level k."""
    # Group models by k
    by_k: dict[int, list[dict]] = {}
    for m in models:
        by_k.setdefault(m["k"], []).append(m)

    results = []
    for k in sorted(by_k.keys()):
        group = by_k[k]
        n = len(group)
        feature_sets = [m["features"] for m in group]
        mean_auc = np.mean([m["auc"] for m in group])
        mean_acc = np.mean([m["accuracy"] for m in group])

        if n < 2:
            results.append({
                "k": k,
                "n_models": n,
                "kuncheva": 1.0 if n == 1 else 0.0,
                "tanimoto": 1.0 if n == 1 else 0.0,
                "cw_rel": 1.0 if n == 1 else 0.0,
                "mean_auc": float(mean_auc),
                "mean_accuracy": float(mean_acc),
            })
            continue

        # Pairwise indices
        kuncheva_vals = []
        tanimoto_vals = []
        for i in range(n):
            for j in range(i + 1, n):
                kuncheva_vals.append(
                    _kuncheva_index(feature_sets[i], feature_sets[j], total_features)
                )
                tanimoto_vals.append(
                    _tanimoto_similarity(feature_sets[i], feature_sets[j])
                )

        cw_rel = _relative_weighted_consistency(feature_sets, total_features)

        results.append({
            "k": k,
            "n_models": n,
            "kuncheva": float(np.mean(kuncheva_vals)),
            "tanimoto": float(np.mean(tanimoto_vals)),
            "cw_rel": float(cw_rel),
            "mean_auc": float(mean_auc),
            "mean_accuracy": float(mean_acc),
        })

    return results


def _compute_dendrogram(models: list[dict]) -> dict:
    """Hierarchical clustering of models using Tanimoto distance."""
    n = len(models)
    if n < 2:
        return {
            "labels": [m["label"] for m in models],
            "merge_matrix": [],
            "distances": [],
            "clusters": [0] * n,
            "n_clusters": 1 if n else 0,
        }

    # Pairwise Tanimoto distance matrix (1 - similarity)
    dist = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            sim = _tanimoto_similarity(models[i]["features"], models[j]["features"])
            d = 1.0 - sim
            dist[i, j] = d
            dist[j, i] = d

    # Condensed distance for scipy
    condensed = squareform(dist)
    Z = linkage(condensed, method="average")

    # Determine number of clusters (cut at distance 0.7)
    clusters = fcluster(Z, t=0.7, criterion="distance")
    n_clusters = int(clusters.max())

    # Convert linkage matrix for JSON serialization
    merge_matrix = Z.tolist()

    # Cluster assignments
    cluster_list = clusters.tolist()

    return {
        "labels": [m["label"] for m in models],
        "merge_matrix": merge_matrix,
        "distances": dist.tolist(),
        "clusters": cluster_list,
        "n_clusters": n_clusters,
    }


def _compute_feature_sparsity_heatmap(
    models: list[dict], feature_names: list[str]
) -> dict:
    """Feature prevalence at each sparsity level.

    Returns a matrix: features (rows) × sparsity levels (columns)
    with values = fraction of models at that k containing the feature.
    """
    # Group by k
    by_k: dict[int, list[dict]] = {}
    for m in models:
        by_k.setdefault(m["k"], []).append(m)
    k_levels = sorted(by_k.keys())

    # Collect all features that appear in any model
    all_used = set()
    for m in models:
        all_used |= m["features"]

    # Sort features by total prevalence (descending)
    total_counts: dict[str, int] = {}
    for m in models:
        for f in m["features"]:
            total_counts[f] = total_counts.get(f, 0) + 1
    sorted_features = sorted(all_used, key=lambda f: -total_counts.get(f, 0))

    # Limit to top 50 for readability
    sorted_features = sorted_features[:50]

    # Build heatmap matrix
    values = []
    for feat in sorted_features:
        row = []
        for k in k_levels:
            group = by_k[k]
            count = sum(1 for m in group if feat in m["features"])
            row.append(count / len(group) if group else 0.0)
        values.append(row)

    return {
        "features": sorted_features,
        "sparsity_levels": k_levels,
        "values": values,
    }


def _compute_distance_matrix(models: list[dict]) -> dict:
    """Pairwise Tanimoto distance matrix (for visualization)."""
    n = len(models)
    if n < 2:
        return {"labels": [m["label"] for m in models], "distances": []}
    # Limit to avoid huge matrices
    if n > 200:
        models = models[:200]
        n = 200
    dist = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            sim = _tanimoto_similarity(models[i]["features"], models[j]["features"])
            dist[i, j] = 1.0 - sim
            dist[j, i] = 1.0 - sim
    return {
        "labels": [m["label"] for m in models],
        "distances": dist.tolist(),
    }


def _empty_result() -> dict:
    """Return an empty stability result."""
    return {
        "stability_by_k": [],
        "dendrogram": {
            "labels": [], "merge_matrix": [], "distances": [],
            "clusters": [], "n_clusters": 0,
        },
        "feature_sparsity_heatmap": {
            "features": [], "sparsity_levels": [], "values": [],
        },
        "model_distance_matrix": {"labels": [], "distances": []},
        "stats": {
            "n_models": 0, "n_features": 0,
            "k_min": 0, "k_max": 0, "peak_stability_k": 0,
        },
    }
