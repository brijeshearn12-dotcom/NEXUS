"""Rule-based pattern flags and anomaly detection for NEXUS criminal network graphs.

Detects:
1. Bridge nodes (articulation points / high betweenness brokers)
2. Cross-case recurrence (entities spanning multiple distinct cases)
3. Density anomalies (unusually high local clustering relative to graph baseline)

Every generated flag includes a complete, auditable reasoning trail.
"""

from __future__ import annotations

import logging
from typing import Any

import networkx as nx

from app.core.db import get_db
from app.services.analytics.centrality import is_valid_person_entity
from app.services.graph.cross_case_linker import find_cross_case_canonical_entities

logger = logging.getLogger(__name__)

# Defensible scientific thresholds for pattern flags
BETWEENNESS_BRIDGE_THRESHOLD = 0.05
LOCAL_CLUSTERING_THRESHOLD = 0.70
DENSITY_RATIO_THRESHOLD = 2.0
MIN_DEGREE_FOR_CLUSTERING = 3


def detect_pattern_flags(
    G: nx.Graph,
    case_id: str,
    database: Any | None = None,
) -> list[dict[str, Any]]:
    """Detect defensible structural pattern flags with evidence-backed reasoning trails.

    Args:
        G: NetworkX graph for the case.
        case_id: Case identifier.
        database: Optional MongoDB database handle.

    Returns:
        List of pattern flag dicts sorted deterministically by severity and entity.
    """
    if G.number_of_nodes() < 3 or G.number_of_edges() < 2:
        return []

    db = database if database is not None else get_db()
    flags: list[dict[str, Any]] = []

    # Precompute topological metrics
    person_nodes = [
        n for n, d in G.nodes(data=True)
        if is_valid_person_entity(n, d)
    ]
    if not person_nodes:
        return []

    betweenness = nx.betweenness_centrality(G, normalized=True)
    try:
        articulation_points = set(nx.articulation_points(G))
    except Exception:
        articulation_points = set()

    global_density = nx.density(G)
    clustering_coeffs = nx.clustering(G)

    # Cross-case mapping from Task 4.1 / Task 4.2 linker
    cross_case_map = find_cross_case_canonical_entities(db) if db is not None else {}

    for node_id in person_nodes:
        node_data = G.nodes.get(node_id, {})
        canonical_name = str(node_data.get("name") or node_id)
        raw_degree = G.degree(node_id)
        bet_val = betweenness.get(node_id, 0.0)
        c_val = clustering_coeffs.get(node_id, 0.0)

        # Collect incident edge metadata and evidence
        incident_edge_refs: list[str] = []
        evidence_snippets: list[str] = []
        incident_doc_refs: set[str] = set()
        node_case_ids: set[str] = {case_id}

        for neighbor in G.neighbors(node_id):
            edge_data = G.get_edge_data(node_id, neighbor, default={})
            edge_id = edge_data.get("edge_id")
            if edge_id:
                incident_edge_refs.append(f"edge:{edge_id}")
            ev = edge_data.get("evidence")
            if ev and ev not in evidence_snippets:
                evidence_snippets.append(ev)
            for doc_id in edge_data.get("document_ids", []):
                incident_doc_refs.add(f"doc:{doc_id}")
            for c_id in edge_data.get("case_ids", []):
                node_case_ids.add(c_id)

        # Check node aliases and cross-case mapping from canonical entity merges (Task 4.1)
        if node_id in cross_case_map:
            node_case_ids.update(cross_case_map[node_id])

        # Also check entity metadata case_ids
        for c_id in node_data.get("metadata", {}).get("case_ids", []):
            if c_id:
                node_case_ids.add(c_id)

        sources = [f"Case ID: {case_id}"]
        if incident_doc_refs:
            sources.extend(sorted([r.replace("doc:", "Document ID: ") for r in incident_doc_refs]))

        # ── 1. BRIDGE NODE FLAG ───────────────────────────────────────────────
        is_articulation = node_id in articulation_points
        is_high_betweenness = bet_val >= BETWEENNESS_BRIDGE_THRESHOLD and raw_degree >= 2

        if (is_articulation and raw_degree >= 2) or is_high_betweenness:
            severity = "high" if is_articulation else "medium"
            reasoning = []
            if is_articulation:
                reasoning.append(
                    "Identified as graph-theoretic articulation point (cut vertex): removing this node disconnects network components.",
                )
            reasoning.append(
                f"Betweenness centrality = {bet_val:.4f} across {raw_degree} incident connections, indicating a critical intermediary role between sub-clusters.",
            )

            flags.append({
                "flag_id": f"flag_bridge_{str(node_id).replace('ent_', '')[:12]}",
                "flag_type": "bridge_node",
                "entity_id": node_id,
                "canonical_name": canonical_name,
                "case_id": case_id,
                "severity": severity,
                "description": (
                    f"Key structural bridge node ({canonical_name}) connecting otherwise separated portions of the network."
                ),
                "trail": {
                    "input_refs": [f"entity:{node_id}"] + incident_edge_refs[:5] + sorted(list(incident_doc_refs))[:2],
                    "evidence": evidence_snippets[:2],
                    "reasoning": reasoning,
                    "result": {
                        "flag_type": "bridge_node",
                        "severity": severity,
                        "articulation_point": is_articulation,
                        "betweenness_centrality": round(bet_val, 4),
                        "degree": raw_degree,
                    },
                    "confidence": 0.90 if is_articulation else 0.85,
                    "source": sources,
                },
            })

        # ── 2. CROSS-CASE RECURRENCE FLAG ─────────────────────────────────────
        if len(node_case_ids) >= 2:
            sorted_cases = sorted(list(node_case_ids))
            flags.append({
                "flag_id": f"flag_cross_{str(node_id).replace('ent_', '')[:12]}",
                "flag_type": "cross_case_recurrence",
                "entity_id": node_id,
                "canonical_name": canonical_name,
                "case_id": case_id,
                "severity": "high",
                "description": (
                    f"Canonical individual ({canonical_name}) recurs across {len(sorted_cases)} distinct cases: {', '.join(sorted_cases)}."
                ),
                "trail": {
                    "input_refs": [f"entity:{node_id}"] + [f"case:{c}" for c in sorted_cases],
                    "evidence": evidence_snippets[:2] or [f"Recurring entity identified across cases: {', '.join(sorted_cases)}"],
                    "reasoning": [
                        f"Canonical identity appears in {len(sorted_cases)} distinct case records based on entity merge records and cross-case edge linkages.",
                        "Demonstrates multi-jurisdictional recurrence within the analyzed criminal network corpus.",
                    ],
                    "result": {
                        "flag_type": "cross_case_recurrence",
                        "severity": "high",
                        "cases_count": len(sorted_cases),
                        "cases": sorted_cases,
                    },
                    "confidence": 0.92,
                    "source": [f"Case ID: {c}" for c in sorted_cases],
                },
            })

        # ── 3. DENSITY ANOMALY FLAG ───────────────────────────────────────────
        if (
            raw_degree >= MIN_DEGREE_FOR_CLUSTERING
            and c_val >= LOCAL_CLUSTERING_THRESHOLD
            and (c_val >= DENSITY_RATIO_THRESHOLD * global_density or global_density < 0.10)
        ):
            ratio = c_val / max(global_density, 0.0001)
            flags.append({
                "flag_id": f"flag_density_{str(node_id).replace('ent_', '')[:12]}",
                "flag_type": "density_anomaly",
                "entity_id": node_id,
                "canonical_name": canonical_name,
                "case_id": case_id,
                "severity": "medium",
                "description": (
                    f"Dense local cluster around ({canonical_name}): local clustering coefficient ({c_val:.3f}) significantly exceeds global baseline ({global_density:.3f})."
                ),
                "trail": {
                    "input_refs": [f"entity:{node_id}"] + incident_edge_refs[:5] + sorted(list(incident_doc_refs))[:2],
                    "evidence": evidence_snippets[:2],
                    "reasoning": [
                        f"Local clustering coefficient = {c_val:.4f} across {raw_degree} neighbors ({round(c_val * 100, 1)}% of neighbor pairs are mutually connected).",
                        f"Exceeds global network density ({global_density:.4f}) by {ratio:.1f}x, indicating a cohesive, tightly bound local clique.",
                    ],
                    "result": {
                        "flag_type": "density_anomaly",
                        "severity": "medium",
                        "local_clustering_coefficient": round(c_val, 4),
                        "global_network_density": round(global_density, 4),
                        "density_ratio": round(ratio, 2),
                        "degree": raw_degree,
                    },
                    "confidence": 0.88,
                    "source": sources,
                },
            })

    # Sort flags deterministically: high severity first, then flag_type, then canonical_name
    severity_order = {"high": 0, "medium": 1, "low": 2}
    flags.sort(
        key=lambda x: (
            severity_order.get(x["severity"], 3),
            x["flag_type"],
            x["canonical_name"].lower(),
            x["flag_id"],
        )
    )

    return flags
