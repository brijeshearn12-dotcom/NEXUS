"""Key individual identification and ranking for NEXUS criminal network graphs.

Combines:
- Degree centrality
- Betweenness centrality
- PageRank
- Louvain community context

Strictly uses neutral structural terminology:
'key individual based on network metrics'
"""

from __future__ import annotations

import logging
from typing import Any

import networkx as nx

from app.services.analytics.centrality import (
    compute_combined_rankings,
)
from app.services.analytics.community import (
    build_node_to_community_map,
    detect_louvain_communities,
)

logger = logging.getLogger(__name__)

NEUTRAL_ROLE_DESCRIPTION = "key individual based on network metrics"


def build_individual_reasoning_trail(
    G: nx.Graph,
    entity_id: str,
    canonical_name: str,
    case_id: str,
    rank: int,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    """Construct an auditable, evidence-backed reasoning trail for a ranked individual.

    Every result includes:
    - input_refs: entities, edges, and documents involved
    - evidence: textual quotes or provenance snippets
    - reasoning: deterministic explanation of calculations
    - result: exact numerical metrics and ranking
    - confidence: bounded confidence value reflecting evidence quality
    - source: case and document provenance references
    """
    raw_deg = metrics.get("raw_degree", G.degree(entity_id))
    deg_val = metrics.get("degree", 0.0)
    bet_val = metrics.get("betweenness", 0.0)
    pr_val = metrics.get("pagerank", 0.0)
    combined_score = metrics.get("combined_score", 0.0)

    # Collect incident edges and evidence snippets
    incident_edge_refs: list[str] = []
    evidence_snippets: list[str] = []
    incident_doc_refs: set[str] = set()
    edge_confidences: list[float] = []

    for neighbor in G.neighbors(entity_id):
        edge_data = G.get_edge_data(entity_id, neighbor, default={})
        edge_id = edge_data.get("edge_id")
        if edge_id:
            incident_edge_refs.append(f"edge:{edge_id}")
        ev = edge_data.get("evidence")
        if ev and ev not in evidence_snippets:
            evidence_snippets.append(ev)
        for doc_id in edge_data.get("document_ids", []):
            incident_doc_refs.add(f"doc:{doc_id}")
        prov = edge_data.get("provenance", {})
        if isinstance(prov, dict) and "confidence" in prov:
            try:
                edge_confidences.append(float(prov["confidence"]))
            except (ValueError, TypeError):
                pass

    # Node's own evidence snippet if available
    node_data = G.nodes.get(entity_id, {})
    node_ev = node_data.get("evidence_snippet")
    if node_ev and node_ev not in evidence_snippets:
        evidence_snippets.append(node_ev)

    input_refs = [f"entity:{entity_id}"] + incident_edge_refs[:5] + sorted(list(incident_doc_refs))[:3]

    reasoning = [
        f"Degree centrality = {deg_val:.4f} because this individual has {raw_deg} direct connections in the analyzed relationship graph.",
        f"Betweenness centrality = {bet_val:.4f} indicating structural brokerage and path traversal between sub-clusters.",
        f"PageRank = {pr_val:.4f} measuring network authority and eigenvector influence across connected entities.",
        f"Combined score = {combined_score:.4f} calculated via documented formula: (0.50 * deg_norm + 0.20 * bet_norm + 0.30 * pr_norm), placing entity at rank {rank}.",
    ]

    # Bounded confidence: average of edge confidences, default 0.85, clamped to [0.70, 0.95]
    if edge_confidences:
        avg_conf = sum(edge_confidences) / len(edge_confidences)
        confidence = round(max(0.70, min(0.95, avg_conf)), 2)
    else:
        confidence = 0.85

    source_refs = [f"Case ID: {case_id}"]
    if incident_doc_refs:
        source_refs.extend(sorted([r.replace("doc:", "Document ID: ") for r in incident_doc_refs]))

    return {
        "input_refs": input_refs,
        "evidence": evidence_snippets[:3],
        "reasoning": reasoning,
        "result": {
            "rank": rank,
            "combined_score": combined_score,
            "raw_degree": raw_deg,
            "degree": deg_val,
            "betweenness": bet_val,
            "pagerank": pr_val,
        },
        "confidence": confidence,
        "source": source_refs,
    }


def rank_key_individuals(
    G: nx.Graph,
    case_id: str,
    communities: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Generate ranked key individuals with Louvain community context and complete reasoning trails.

    Args:
        G: NetworkX graph.
        case_id: Case string identifier.
        communities: Optional precomputed Louvain communities.

    Returns:
        List of ranked key individuals with deterministic scores, ranks, and reasoning trails.
    """
    if communities is None:
        communities = detect_louvain_communities(G)

    node_to_comm = build_node_to_community_map(communities)
    ranked_metrics = compute_combined_rankings(G)

    key_individuals: list[dict[str, Any]] = []

    for item in ranked_metrics:
        ent_id = item["entity_id"]
        canonical_name = item["canonical_name"]
        rank = item["rank"]
        comm_id = node_to_comm.get(ent_id)

        trail = build_individual_reasoning_trail(
            G=G,
            entity_id=ent_id,
            canonical_name=canonical_name,
            case_id=case_id,
            rank=rank,
            metrics=item,
        )

        key_individuals.append({
            "entity_id": ent_id,
            "canonical_name": canonical_name,
            "degree": item["degree"],
            "raw_degree": item["raw_degree"],
            "betweenness": item["betweenness"],
            "pagerank": item["pagerank"],
            "combined_score": item["combined_score"],
            "rank": rank,
            "community_id": comm_id,
            "role_description": NEUTRAL_ROLE_DESCRIPTION,
            "trail": trail,
        })

    return key_individuals
