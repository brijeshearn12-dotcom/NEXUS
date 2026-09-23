"""Louvain community detection for NEXUS criminal network graphs.

Identifies cohesive structural sub-clusters within the analyzed case network.
"""

from __future__ import annotations

import logging
from typing import Any

import networkx as nx
from networkx.algorithms.community import louvain_communities

from app.services.analytics.centrality import MIN_GRAPH_EDGES, MIN_GRAPH_NODES

logger = logging.getLogger(__name__)


def detect_louvain_communities(
    G: nx.Graph,
    seed: int = 42,
    min_community_size: int = 2,
) -> list[dict[str, Any]]:
    """Execute deterministic Louvain community detection on a NetworkX graph.

    Args:
        G: NetworkX graph.
        seed: Random seed for deterministic partition convergence.
        min_community_size: Minimum member threshold for a cluster (filters isolated singletons).

    Returns:
        List of communities, each containing:
        - community_id: str (e.g. 'comm_1')
        - member_ids: list[str] (sorted entity IDs)
        - member_names: list[str] (canonical names)
        - size: int (member count)
    """
    if G.number_of_nodes() < MIN_GRAPH_NODES or G.number_of_edges() < MIN_GRAPH_EDGES:
        return []

    try:
        raw_communities = louvain_communities(G, weight="weight", seed=seed)
    except Exception as exc:
        logger.warning("Louvain community detection failed: %s", exc)
        return []

    # Filter communities to those with >= min_community_size
    valid_clusters = [
        c for c in raw_communities
        if len(c) >= min_community_size
    ]

    # Deterministic sorting: size descending, then smallest member ID ascending
    sorted_clusters = sorted(
        valid_clusters,
        key=lambda c: (-len(c), sorted(list(c))[0] if c else ""),
    )

    formatted_communities: list[dict[str, Any]] = []
    for idx, cluster in enumerate(sorted_clusters, start=1):
        member_ids = sorted(list(cluster))
        member_names = [
            str(G.nodes[n].get("name") or n)
            for n in member_ids
        ]
        formatted_communities.append({
            "community_id": f"comm_{idx}",
            "member_ids": member_ids,
            "member_names": member_names,
            "size": len(member_ids),
        })

    return formatted_communities


def build_node_to_community_map(communities: list[dict[str, Any]]) -> dict[str, str]:
    """Map each entity_id to its assigned community_id."""
    node_map: dict[str, str] = {}
    for comm in communities:
        comm_id = comm["community_id"]
        for node_id in comm["member_ids"]:
            node_map[node_id] = comm_id
    return node_map
