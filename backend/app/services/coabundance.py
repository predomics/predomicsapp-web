"""Co-abundance ecosystem network service.

Computes species co-abundance networks from the abundance matrix using
Spearman correlation, with community detection (Louvain) and taxonomic
coloring inspired by the Interpred approach and SCAPIS ecosystem code.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from . import msp_annotations
from .taxonomy_colors import assign_taxonomy_colors, MODULE_COLORS

logger = logging.getLogger(__name__)

# TTL cache for network computation results
_cache: dict[tuple, tuple[float, dict]] = {}
_CACHE_TTL = 600  # 10 minutes


def _cache_key(
    x_path: str, y_path: str, min_prevalence_pct: float,
    correlation_threshold: float, class_filter: str,
    features_csv: str,
) -> tuple:
    return (x_path, y_path, min_prevalence_pct, correlation_threshold, class_filter, features_csv)


def _get_cached(key: tuple) -> dict | None:
    if key in _cache:
        ts, result = _cache[key]
        if time.time() - ts < _CACHE_TTL:
            return result
        del _cache[key]
    return None


def _set_cached(key: tuple, result: dict) -> None:
    _cache[key] = (time.time(), result)
    if len(_cache) > 10:
        now = time.time()
        expired = [k for k, (ts, _) in _cache.items() if now - ts > _CACHE_TTL]
        for k in expired:
            del _cache[k]


def compute_coabundance_network(
    x_path: str,
    y_path: str,
    features_in_rows: bool = True,
    min_prevalence_pct: float = 30.0,
    correlation_threshold: float = 0.3,
    class_filter: str = "all",
    feature_names: list[str] | None = None,
    job_results: dict | None = None,
) -> dict[str, Any]:
    """Compute a co-abundance network from the abundance matrix.

    Args:
        x_path: Path to Xtrain TSV file.
        y_path: Path to Ytrain TSV file.
        features_in_rows: Whether features are in rows (transposed to samples×features).
        min_prevalence_pct: Minimum prevalence (%) to include a feature.
        correlation_threshold: Minimum |Spearman rho| for an edge.
        class_filter: "all", "0", or "1" — which class samples to use.
        feature_names: Optional feature subset (e.g., FBM features from a job).
        job_results: Optional job results dict for FBM annotation.

    Returns:
        Dict with nodes, edges, modules, taxonomy_legend, stats.
    """
    features_csv = ",".join(sorted(feature_names)) if feature_names else ""
    key = _cache_key(x_path, y_path, min_prevalence_pct, correlation_threshold, class_filter, features_csv)
    cached = _get_cached(key)
    if cached is not None:
        return cached

    t0 = time.time()

    # --- Load data ---
    X = pd.read_csv(x_path, sep="\t", index_col=0)
    y = pd.read_csv(y_path, sep="\t", index_col=0)

    if features_in_rows:
        X = X.T  # rows=samples, cols=features

    y_series = y.iloc[:, 0]
    common = X.index.intersection(y_series.index)
    X = X.loc[common]
    y_series = y_series.loc[common]

    n_features_total = X.shape[1]

    # --- Filter to specific features if provided ---
    if feature_names:
        valid = [f for f in feature_names if f in X.columns]
        if valid:
            X = X[valid]

    # --- Filter by class ---
    if class_filter in ("0", "1"):
        cls_val = int(class_filter)
        mask = y_series == cls_val
        X = X.loc[mask]
        y_series = y_series.loc[mask]

    # --- Filter features by prevalence ---
    n_samples = X.shape[0]
    prevalence = (X > 0).sum(axis=0) / n_samples * 100
    kept_features = prevalence[prevalence >= min_prevalence_pct].index.tolist()

    if len(kept_features) < 2:
        return _empty_result(n_features_total)

    X_filtered = X[kept_features]
    n_features_filtered = len(kept_features)

    # --- Compute per-class prevalence for all samples ---
    X_full = pd.read_csv(x_path, sep="\t", index_col=0)
    if features_in_rows:
        X_full = X_full.T
    y_full = pd.read_csv(y_path, sep="\t", index_col=0).iloc[:, 0]
    common_full = X_full.index.intersection(y_full.index)
    X_full = X_full.loc[common_full]
    y_full = y_full.loc[common_full]

    class_labels = sorted([str(int(c)) for c in y_full.unique()])
    prevalence_by_class: dict[str, dict[str, float]] = {}
    for cls_label in class_labels:
        cls_mask = y_full == int(cls_label)
        n_cls = cls_mask.sum()
        if n_cls > 0 and all(f in X_full.columns for f in kept_features):
            prev = (X_full.loc[cls_mask, kept_features] > 0).sum(axis=0) / n_cls
            prevalence_by_class[cls_label] = prev.to_dict()
        else:
            prevalence_by_class[cls_label] = {f: 0.0 for f in kept_features}

    # --- Compute pairwise Spearman correlations ---
    mat = X_filtered.values.astype(float)
    mat = np.nan_to_num(mat, nan=0.0)

    n_feat = mat.shape[1]
    corr_matrix = np.zeros((n_feat, n_feat))
    pval_matrix = np.ones((n_feat, n_feat))

    # Use scipy spearmanr for the full matrix at once if feasible
    if n_feat <= 1000:
        rho, pval = stats.spearmanr(mat, axis=0)
        if n_feat == 2:
            # spearmanr returns scalars for 2 variables
            corr_matrix = np.array([[1.0, rho], [rho, 1.0]])
            pval_matrix = np.array([[0.0, pval], [pval, 0.0]])
        else:
            corr_matrix = rho
            pval_matrix = pval
    else:
        # For very large feature sets, compute pairwise
        for i in range(n_feat):
            for j in range(i + 1, n_feat):
                r, p = stats.spearmanr(mat[:, i], mat[:, j])
                corr_matrix[i, j] = corr_matrix[j, i] = r
                pval_matrix[i, j] = pval_matrix[j, i] = p
            corr_matrix[i, i] = 1.0

    # --- Build edge list ---
    edges = []
    for i in range(n_feat):
        for j in range(i + 1, n_feat):
            rho = corr_matrix[i, j]
            if np.isnan(rho):
                continue
            if abs(rho) >= correlation_threshold:
                edges.append({
                    "source": kept_features[i],
                    "target": kept_features[j],
                    "correlation": round(float(rho), 4),
                    "pvalue": round(float(pval_matrix[i, j]), 6),
                })

    if not edges:
        return _empty_result(n_features_total, n_features_filtered)

    # --- Build networkx graph + community detection ---
    import networkx as nx

    G = nx.Graph()
    # Add all filtered features as nodes (even isolated ones after edge filtering)
    edge_nodes = set()
    for e in edges:
        edge_nodes.add(e["source"])
        edge_nodes.add(e["target"])
        G.add_edge(e["source"], e["target"], weight=abs(e["correlation"]))

    # Only include nodes that have at least one edge
    node_ids = sorted(edge_nodes)

    # Community detection (Louvain)
    try:
        communities = nx.community.louvain_communities(G, seed=42)
        modularity = nx.community.modularity(G, communities)
    except Exception:
        communities = [{n} for n in node_ids]
        modularity = 0.0

    node_module: dict[str, int] = {}
    for mod_idx, comm in enumerate(communities):
        for n in comm:
            node_module[n] = mod_idx

    # Node metrics
    degrees = dict(G.degree())
    try:
        betweenness = nx.betweenness_centrality(G)
    except Exception:
        betweenness = {n: 0.0 for n in node_ids}

    # Mean abundance per feature
    mean_abundance = X_filtered.mean(axis=0).to_dict()

    # --- Fetch taxonomy annotations ---
    annotations = msp_annotations.get_annotations(node_ids)

    # --- Build node list ---
    nodes_for_coloring = []
    for nid in node_ids:
        ann = annotations.get(nid, {})
        nodes_for_coloring.append({
            "id": nid,
            "phylum": ann.get("phylum", None),
            "family": ann.get("family", None),
        })

    family_colors, legend_entries = assign_taxonomy_colors(nodes_for_coloring)

    # --- FBM annotation (if job results provided) ---
    fbm_data = _compute_fbm_annotation(job_results, node_ids) if job_results else {}

    # --- Assemble nodes ---
    nodes = []
    for nid in node_ids:
        ann = annotations.get(nid, {})
        phy = ann.get("phylum", "Unknown")
        fam = ann.get("family", "Unknown")

        prev_0 = prevalence_by_class.get("0", {}).get(nid, 0.0)
        prev_1 = prevalence_by_class.get("1", {}).get(nid, 0.0)
        enriched = 1 if prev_1 > prev_0 else 0

        fbm = fbm_data.get(nid, {})

        nodes.append({
            "id": nid,
            "species": ann.get("species", nid),
            "phylum": phy,
            "family": fam,
            "genus": ann.get("genus", None),
            "color": family_colors.get(fam, "#999999"),
            "module": node_module.get(nid, 0),
            "degree": degrees.get(nid, 0),
            "betweenness": round(betweenness.get(nid, 0.0), 4),
            "mean_abundance": round(mean_abundance.get(nid, 0.0), 6),
            "prevalence_0": round(prev_0, 4),
            "prevalence_1": round(prev_1, 4),
            "enriched_class": enriched,
            "fbm_prevalence": fbm.get("prevalence"),
            "fbm_coefficient": fbm.get("coefficient"),
        })

    # --- Assemble modules ---
    modules = []
    for mod_idx, comm in enumerate(communities):
        # Only include modules that have nodes in our final node set
        comm_in_nodes = comm.intersection(edge_nodes)
        if not comm_in_nodes:
            continue
        # Dominant phylum
        phyla = [annotations.get(n, {}).get("phylum", "Unknown") for n in comm_in_nodes]
        if phyla:
            from collections import Counter
            dominant = Counter(phyla).most_common(1)[0][0]
        else:
            dominant = "Unknown"

        modules.append({
            "id": mod_idx,
            "size": len(comm_in_nodes),
            "color": MODULE_COLORS[mod_idx % len(MODULE_COLORS)],
            "dominant_phylum": dominant,
        })

    elapsed = time.time() - t0
    logger.info(
        "Co-abundance network: %d nodes, %d edges, %d modules (%.1fs)",
        len(nodes), len(edges), len(modules), elapsed,
    )

    result = {
        "nodes": nodes,
        "edges": edges,
        "modules": modules,
        "taxonomy_legend": legend_entries,
        "stats": {
            "n_features_total": n_features_total,
            "n_features_filtered": n_features_filtered,
            "n_nodes": len(nodes),
            "n_edges": len(edges),
            "n_modules": len(modules),
            "modularity": round(modularity, 4),
        },
    }

    _set_cached(key, result)
    return result


def _compute_fbm_annotation(
    job_results: dict, feature_ids: list[str],
) -> dict[str, dict]:
    """Extract FBM prevalence and dominant coefficient for each feature."""
    population = job_results.get("population", [])
    if not population:
        return {}

    n_models = len(population)
    feature_counts: dict[str, int] = {}
    coeff_sums: dict[str, int] = {}

    for ind in population:
        named = ind.get("named_features", {})
        for feat, coeff in named.items():
            if feat in feature_ids:
                feature_counts[feat] = feature_counts.get(feat, 0) + 1
                coeff_sums[feat] = coeff_sums.get(feat, 0) + int(coeff)

    result = {}
    for feat in feature_ids:
        count = feature_counts.get(feat, 0)
        if count > 0:
            result[feat] = {
                "prevalence": round(count / n_models, 4),
                "coefficient": 1 if coeff_sums.get(feat, 0) > 0 else (-1 if coeff_sums.get(feat, 0) < 0 else 0),
            }
    return result


def _empty_result(n_total: int = 0, n_filtered: int = 0) -> dict:
    return {
        "nodes": [],
        "edges": [],
        "modules": [],
        "taxonomy_legend": [],
        "stats": {
            "n_features_total": n_total,
            "n_features_filtered": n_filtered,
            "n_nodes": 0,
            "n_edges": 0,
            "n_modules": 0,
            "modularity": 0.0,
        },
    }
