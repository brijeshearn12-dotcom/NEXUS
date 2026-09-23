"""
noordin_loader.py — Load Noordin Top validation dataset for graph algorithm benchmarking.

SIH26189GREEN | Criminal Network Analysis System
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def get_validation_dir() -> Path:
    """Return the data/validation directory path."""
    current = Path(__file__).resolve()
    # backend/app/services/validation/noordin_loader.py -> backend -> NEXUS -> data/validation
    repo_root = current.parents[4]
    return repo_root / "data" / "validation"


def load_noordin_metadata() -> dict[str, Any]:
    """Load metadata describing the Noordin Top dataset."""
    val_dir = get_validation_dir()
    meta_file = val_dir / "noordin_top_metadata.json"
    if not meta_file.exists():
        raise FileNotFoundError(f"Noordin Top metadata file not found at {meta_file}")
    with open(meta_file, encoding="utf-8") as fp:
        return json.load(fp)


def load_edge_file(filename: str) -> list[dict[str, Any]]:
    """Load an edge list CSV by filename."""
    val_dir = get_validation_dir()
    file_path = val_dir / filename
    if not file_path.exists():
        raise FileNotFoundError(f"Validation edge file not found: {file_path}")

    edges: list[dict[str, Any]] = []
    with open(file_path, encoding="utf-8") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            if not row or not row.get("source"):
                continue
            edges.append(
                {
                    "source": row["source"],
                    "target": row["target"],
                    "relationship": row.get("relationship", ""),
                    "confidence": float(row.get("confidence", 1.0)),
                    "source_reference": row.get("source_reference", ""),
                }
            )
    return edges


def load_communication_edges() -> list[dict[str, Any]]:
    return load_edge_file("communication_edges.csv")


def load_operational_edges() -> list[dict[str, Any]]:
    return load_edge_file("operational_edges.csv")


def load_trust_edges() -> list[dict[str, Any]]:
    return load_edge_file("trust_edges.csv")


import logging

import networkx as nx

logger = logging.getLogger(__name__)


def load_financial_edges() -> list[dict[str, Any]]:
    return load_edge_file("financial_edges.csv")


def load_all_noordin_edges() -> dict[str, list[dict[str, Any]]]:
    """Load all categorized edge lists for validation benchmarking."""
    return {
        "communication": load_communication_edges(),
        "operational": load_operational_edges(),
        "trust": load_trust_edges(),
        "financial": load_financial_edges(),
    }


def build_noordin_graph() -> nx.Graph:
    """Construct a NetworkX Graph from the Noordin Top multi-relational validation dataset.

    Normalizes nodes and edges to conform exactly with the NEXUS case graph schema,
    enabling direct reuse of Task 5.1 analytics functions (centrality, Louvain communities,
    deterministic combined ranking, and evidence-backed reasoning trails).
    """
    edges_by_cat = load_all_noordin_edges()
    G = nx.Graph()

    for category, edge_list in edges_by_cat.items():
        for e in edge_list:
            src = str(e.get("source", "")).strip()
            tgt = str(e.get("target", "")).strip()
            if not src or not tgt:
                continue

            for node_id in (src, tgt):
                if not G.has_node(node_id):
                    G.add_node(
                        node_id,
                        id=node_id,
                        name=node_id,
                        entity_type="PERSON",
                        verification_status="verified",
                        aliases=[],
                        case_id="noordin_top",
                        evidence_snippet="Actor in Noordin Top covert dark network documented in ICG Report No. 114",
                    )

            weight = float(e.get("confidence", 1.0))
            rel = str(e.get("relationship", category)).upper()
            ref = str(e.get("source_reference", "ICG Report No. 114 / Everton (2012)"))

            if G.has_edge(src, tgt):
                existing_w = G[src][tgt].get("weight", 1.0)
                G[src][tgt]["weight"] = round(existing_w + weight, 2)
                if "edge_types" in G[src][tgt] and rel not in G[src][tgt]["edge_types"]:
                    G[src][tgt]["edge_types"].append(rel)
            else:
                G.add_edge(
                    src,
                    tgt,
                    weight=weight,
                    edge_type=rel,
                    edge_types=[rel],
                    relationship=rel,
                    verification_status="verified",
                    evidence=f"{rel} tie documented in {ref}",
                    provenance={
                        "tier": "primary",
                        "source_ref": ref,
                        "method": "historical_literature",
                        "confidence": weight,
                    },
                    case_ids=["noordin_top"],
                    document_ids=["icg_report_114"],
                )

    logger.info(
        "Built Noordin validation graph: %d nodes, %d edges across 4 relationship categories",
        G.number_of_nodes(),
        G.number_of_edges(),
    )
    return G


def run_noordin_validation(top_k: int = 5) -> dict[str, Any]:
    """Execute the exact Task 5.1 analytics pipeline against the Noordin Top ground-truth network.

    Reuses without modification:
    - compute_centrality_metrics (degree, betweenness, PageRank)
    - compute_combined_rankings (deterministic 0.50/0.20/0.30 formula)
    - detect_louvain_communities
    - rank_key_individuals (complete reasoning trails)

    Strict scientific principle:
    - Never changes weights, thresholds, or ranking logic to inflate the score.
    - Matches purely against documented ground truth from Roberts & Everton / ICG Report No. 114.
    """
    from app.services.analytics.centrality import (
        MIN_GRAPH_EDGES,
        MIN_GRAPH_NODES,
        compute_centrality_metrics,
    )
    from app.services.analytics.community import detect_louvain_communities
    from app.services.analytics.key_individuals import rank_key_individuals

    metadata = load_noordin_metadata()
    G = build_noordin_graph()

    num_nodes = G.number_of_nodes()
    num_edges = G.number_of_edges()

    if num_nodes < MIN_GRAPH_NODES or num_edges < MIN_GRAPH_EDGES:
        return {
            "status": "insufficient_data",
            "dataset": metadata.get("dataset_name", "Noordin Top"),
            "reason": (
                f"Graph has {num_nodes} node(s) and {num_edges} edge(s). "
                f"Minimum required: {MIN_GRAPH_NODES} nodes and {MIN_GRAPH_EDGES} edges."
            ),
            "ground_truth_count": 0,
            "top_k": top_k,
            "matches": 0,
            "score": "0 of 0 match documented figures",
        }

    # Run the EXACT Task 5.1 analytics functions
    communities = detect_louvain_communities(G)
    ranked_individuals = rank_key_individuals(
        G=G,
        case_id="noordin_top",
        communities=communities,
    )
    centrality_metrics = compute_centrality_metrics(G)

    # Documented Ground Truth from metadata
    benchmark_metrics = metadata.get("benchmark_metrics", {})
    raw_key_actors = benchmark_metrics.get("key_actors", [])

    ground_truth_figures: list[dict[str, str]] = []
    for entry in raw_key_actors:
        parts = entry.split(" (", 1)
        name = parts[0].strip()
        role = parts[1].rstrip(")") if len(parts) > 1 else "Key Operative"
        ground_truth_figures.append({"name": name, "documented_role": role})

    gt_dict = {f["name"]: f["documented_role"] for f in ground_truth_figures}
    effective_top_k = max(1, min(top_k, len(ranked_individuals)))
    top_k_individuals = ranked_individuals[:effective_top_k]

    matching_figures: list[dict[str, Any]] = []
    for item in top_k_individuals:
        c_name = item["canonical_name"]
        if c_name in gt_dict:
            matching_figures.append({
                "rank": item["rank"],
                "name": c_name,
                "combined_score": item["combined_score"],
                "documented_role": gt_dict[c_name],
            })

    top_k_names_set = {item["canonical_name"] for item in top_k_individuals}
    unmatched_ground_truth: list[dict[str, Any]] = []
    for gt in ground_truth_figures:
        if gt["name"] not in top_k_names_set:
            actual_rank = None
            actual_score = None
            for item in ranked_individuals:
                if item["canonical_name"] == gt["name"]:
                    actual_rank = item["rank"]
                    actual_score = item["combined_score"]
                    break
            unmatched_ground_truth.append({
                "name": gt["name"],
                "documented_role": gt["documented_role"],
                "actual_rank": actual_rank,
                "actual_combined_score": actual_score,
            })

    matches_count = len(matching_figures)
    score_str = f"{matches_count} of top {effective_top_k} match documented figures"
    score_pct = round((matches_count / effective_top_k) * 100, 1) if effective_top_k > 0 else 0.0

    return {
        "status": "ok",
        "dataset": {
            "name": metadata.get("dataset_name", "Noordin Top"),
            "network_type": metadata.get("network_type", ""),
            "node_count": num_nodes,
            "edge_count": num_edges,
            "relationship_categories": ["communication", "operational", "trust", "financial"],
            "financial_edges_status": "0 rows (header only, zero pairwise transactions fabricated)",
        },
        "source_reference": {
            "citation": metadata.get("citation", ""),
            "primary_source_document": metadata.get("primary_source_document", ""),
            "academic_reference": metadata.get("academic_reference", ""),
            "doi": metadata.get("doi", ""),
            "source_repository": metadata.get("source_repository", ""),
        },
        "ground_truth_count": len(ground_truth_figures),
        "top_k": effective_top_k,
        "matches": matches_count,
        "score": score_str,
        "score_percentage": score_pct,
        "ground_truth_figures": ground_truth_figures,
        "top_ranked_individuals": top_k_individuals,
        "matching_figures": matching_figures,
        "unmatched_ground_truth": unmatched_ground_truth,
        "ranked_individuals": ranked_individuals,
        "communities": communities,
        "centrality_metrics": {
            "degree_centrality": centrality_metrics["degree_centrality"],
            "raw_degree": centrality_metrics["raw_degree"],
            "betweenness_centrality": centrality_metrics["betweenness_centrality"],
            "pagerank": centrality_metrics["pagerank"],
        },
        "validation_limitations": metadata.get("limitations", []),
        "legal_notice": (
            "Validation measures agreement with documented network figures; "
            "it does not establish legal guilt, responsibility, or intent."
        ),
    }
