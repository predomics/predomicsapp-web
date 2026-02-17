"""Model stability analysis service.

Computes stability indices for the Family of Best Models (FBM) population,
inspired by the Shasha Cui internship (Ecole Polytechnique / ICAN, 2017).

Provides:
- Stability indices per sparsity level (Kuncheva, Tanimoto, CW_rel)
- Hierarchical clustering of models (Tanimoto distance)
- Feature prevalence heatmap across sparsity levels

Optimised: uses numpy binary vectors for fast vectorized Tanimoto,
computes the distance matrix once, caps models for dendrogram.
"""

from __future__ import annotations

import logging
import time

import numpy as np
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform

logger = logging.getLogger(__name__)

# Cap for dendrogram / distance matrix to keep response fast
_MAX_DENDRO_MODELS = 100


# ---------------------------------------------------------------------------
# Vectorised Tanimoto distance
# ---------------------------------------------------------------------------

def _build_binary_matrix(models: list[dict], feature_to_idx: dict[str, int]) -> np.ndarray:
    """Build an (n_models × n_features) binary matrix.  Fast path."""
    n = len(models)
    p = len(feature_to_idx)
    mat = np.zeros((n, p), dtype=np.float32)
    for i, m in enumerate(models):
        for f in m["features"]:
            j = feature_to_idx.get(f)
            if j is not None:
                mat[i, j] = 1.0
    return mat


def _tanimoto_distance_matrix(mat: np.ndarray) -> np.ndarray:
    """Vectorised pairwise Tanimoto distance for binary matrix.

    Tanimoto sim = |A∩B| / |A∪B| = dot / (|A| + |B| - dot)
    Distance = 1 - sim.  O(n² · p) but via numpy BLAS → very fast.
    """
    # Intersection counts via matrix multiply
    dots = mat @ mat.T  # (n, n)
    # Row sums = feature counts per model
    sums = mat.sum(axis=1)  # (n,)
    # Union = |A| + |B| - |A∩B|
    sums_i = sums[:, None]
    sums_j = sums[None, :]
    union = sums_i + sums_j - dots
    # Avoid division by zero
    union = np.maximum(union, 1e-10)
    sim = dots / union
    np.fill_diagonal(sim, 1.0)
    return 1.0 - sim


# ---------------------------------------------------------------------------
# Stability indices
# ---------------------------------------------------------------------------

def _kuncheva_from_binary(group_mat: np.ndarray, total_features: int) -> float:
    """Mean pairwise Kuncheva index from binary sub-matrix.

    κ = (|A∩B| - d²/c) / (d(1 - d/c))  averaged over all pairs.
    """
    n = group_mat.shape[0]
    if n < 2:
        return 1.0
    dots = group_mat @ group_mat.T
    sums = group_mat.sum(axis=1)
    c = total_features
    total = 0.0
    count = 0
    for i in range(n):
        d_i = sums[i]
        for j in range(i + 1, n):
            d = (d_i + sums[j]) / 2  # average k for mixed-k groups
            if d <= 0 or d >= c:
                continue
            intersection = dots[i, j]
            num = intersection - (d * d / c)
            den = d * (1 - d / c)
            if den > 0:
                total += num / den
            count += 1
    return total / count if count > 0 else 0.0


def _cw_rel_from_binary(group_mat: np.ndarray, total_features: int) -> float:
    """Relative weighted consistency from binary sub-matrix."""
    n = group_mat.shape[0]
    if n <= 1:
        return 1.0
    freq = group_mat.sum(axis=0)  # per-feature count
    total_n = freq.sum()
    if total_n == 0:
        return 0.0
    cw = float(np.sum((freq / total_n) * ((freq - 1) / (n - 1))))
    d = float(group_mat.sum(axis=1).mean())
    c = total_features
    cw_min = d / c if c > 0 else 0.0
    denom = 1.0 - cw_min
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
    """Compute stability analysis for a model population."""
    t0 = time.monotonic()

    if not population or not feature_names:
        return _empty_result()

    total_features = len(feature_names)

    # Build feature name → index lookup
    feat_to_idx: dict[str, int] = {}
    feat_idx_counter = 0

    # Extract feature sets per model
    models = []
    for i, ind in enumerate(population):
        metrics = ind.get("metrics", {})
        features = ind.get("features", {})
        named = ind.get("named_features", {})
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

        # Register features
        for f in feat_set:
            if f not in feat_to_idx:
                feat_to_idx[f] = feat_idx_counter
                feat_idx_counter += 1

        models.append({
            "index": i,
            "k": metrics.get("k", len(feat_set)),
            "auc": metrics.get("auc", 0.0),
            "accuracy": metrics.get("accuracy", 0.0),
            "features": feat_set,
            "label": f"M{i}_k{metrics.get('k', len(feat_set))}",
        })

    # Build binary matrix (all models × all used features)
    bin_mat = _build_binary_matrix(models, feat_to_idx)

    # --- 1. Stability by sparsity level (k) ---
    stability_by_k = _compute_stability_by_k(models, bin_mat, total_features)

    # --- 2 & 3. Dendrogram + distance matrix (capped) ---
    n = len(models)
    if n > _MAX_DENDRO_MODELS:
        # Sample evenly across models
        step = n / _MAX_DENDRO_MODELS
        indices = [int(i * step) for i in range(_MAX_DENDRO_MODELS)]
        sub_models = [models[i] for i in indices]
        sub_mat = bin_mat[indices]
    else:
        sub_models = models
        sub_mat = bin_mat

    dist = _tanimoto_distance_matrix(sub_mat)
    dendrogram_data = _compute_dendrogram_from_dist(sub_models, dist)

    # --- 4. Feature × sparsity heatmap ---
    heatmap = _compute_feature_sparsity_heatmap(models)

    # Stats
    k_values = [m["k"] for m in models]
    peak_k = 0
    if stability_by_k:
        best_entry = max(stability_by_k, key=lambda x: x["tanimoto"])
        peak_k = best_entry["k"]

    elapsed = time.monotonic() - t0
    logger.info("Stability analysis: %d models, %.1f ms", n, elapsed * 1000)

    return {
        "stability_by_k": stability_by_k,
        "dendrogram": dendrogram_data,
        "feature_sparsity_heatmap": heatmap,
        "stats": {
            "n_models": len(models),
            "n_features": total_features,
            "k_min": min(k_values) if k_values else 0,
            "k_max": max(k_values) if k_values else 0,
            "peak_stability_k": peak_k,
        },
    }


def _compute_stability_by_k(
    models: list[dict], bin_mat: np.ndarray, total_features: int,
) -> list[dict]:
    """Compute stability indices grouped by sparsity level k."""
    by_k: dict[int, list[int]] = {}  # k -> list of model indices
    for i, m in enumerate(models):
        by_k.setdefault(m["k"], []).append(i)

    results = []
    for k in sorted(by_k.keys()):
        idxs = by_k[k]
        n = len(idxs)
        group_mat = bin_mat[idxs]
        mean_auc = float(np.mean([models[i]["auc"] for i in idxs]))
        mean_acc = float(np.mean([models[i]["accuracy"] for i in idxs]))

        if n < 2:
            results.append({
                "k": k, "n_models": n,
                "kuncheva": 1.0 if n == 1 else 0.0,
                "tanimoto": 1.0 if n == 1 else 0.0,
                "cw_rel": 1.0 if n == 1 else 0.0,
                "mean_auc": mean_auc, "mean_accuracy": mean_acc,
            })
            continue

        # Cap pairwise to avoid excessive computation
        if n > 80:
            sample = np.random.default_rng(42).choice(n, 80, replace=False)
            group_mat_sample = group_mat[sample]
        else:
            group_mat_sample = group_mat

        # Vectorised Tanimoto mean
        dist_sub = _tanimoto_distance_matrix(group_mat_sample)
        n_s = dist_sub.shape[0]
        mask = np.triu(np.ones((n_s, n_s), dtype=bool), k=1)
        mean_tanimoto = float(1.0 - dist_sub[mask].mean())

        kuncheva = float(_kuncheva_from_binary(group_mat_sample, total_features))
        cw_rel = float(_cw_rel_from_binary(group_mat, total_features))

        results.append({
            "k": k, "n_models": n,
            "kuncheva": kuncheva,
            "tanimoto": mean_tanimoto,
            "cw_rel": cw_rel,
            "mean_auc": mean_auc, "mean_accuracy": mean_acc,
        })

    return results


def _compute_dendrogram_from_dist(models: list[dict], dist: np.ndarray) -> dict:
    """Hierarchical clustering from precomputed distance matrix.

    Returns linkage matrix and leaf ordering for dendrogram rendering.
    """
    n = len(models)
    if n < 2:
        return {
            "labels": [m["label"] for m in models],
            "clusters": [1] * n,
            "n_clusters": 1 if n else 0,
            "linkage": [],
            "leaf_order": list(range(n)),
        }

    condensed = squareform(dist, checks=False)
    Z = linkage(condensed, method="average")
    clusters = fcluster(Z, t=0.7, criterion="distance")

    # Compute leaf ordering via dendrogram (without plotting)
    from scipy.cluster.hierarchy import leaves_list
    leaf_order = leaves_list(Z).tolist()

    return {
        "labels": [m["label"] for m in models],
        "clusters": clusters.tolist(),
        "n_clusters": int(clusters.max()),
        "linkage": Z.tolist(),  # [idx1, idx2, dist, count] per merge
        "leaf_order": leaf_order,
        "n_models_shown": n,
    }


def _compute_feature_sparsity_heatmap(models: list[dict]) -> dict:
    """Feature prevalence at each sparsity level."""
    by_k: dict[int, list[dict]] = {}
    for m in models:
        by_k.setdefault(m["k"], []).append(m)
    k_levels = sorted(by_k.keys())

    # Count per feature
    total_counts: dict[str, int] = {}
    for m in models:
        for f in m["features"]:
            total_counts[f] = total_counts.get(f, 0) + 1

    sorted_features = sorted(total_counts.keys(), key=lambda f: -total_counts[f])
    sorted_features = sorted_features[:50]

    values = []
    for feat in sorted_features:
        row = []
        for k in k_levels:
            group = by_k[k]
            count = sum(1 for m in group if feat in m["features"])
            row.append(round(count / len(group), 3) if group else 0.0)
        values.append(row)

    return {
        "features": sorted_features,
        "sparsity_levels": k_levels,
        "values": values,
    }


def _empty_result() -> dict:
    return {
        "stability_by_k": [],
        "dendrogram": {"labels": [], "clusters": [], "n_clusters": 0},
        "feature_sparsity_heatmap": {
            "features": [], "sparsity_levels": [], "values": [],
        },
        "stats": {
            "n_models": 0, "n_features": 0,
            "k_min": 0, "k_max": 0, "peak_stability_k": 0,
        },
    }
