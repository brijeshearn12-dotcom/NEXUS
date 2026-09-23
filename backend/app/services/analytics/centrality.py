"""Centrality analytics for NEXUS criminal network graphs.

Computes:
- Degree centrality
- Betweenness centrality
- PageRank
- Combined deterministic ranking

Explicitly restricts ranking to actual PERSON entities.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import networkx as nx

from app.services.graph.edge_rules import is_valid_accused_person

logger = logging.getLogger(__name__)

# Minimum thresholds for meaningful network graph analysis
MIN_GRAPH_NODES = 3
MIN_GRAPH_EDGES = 2
MIN_PERSON_NODES = 1

# Procedural and non-person stopwords that can arise from judicial NLP
PROCEDURAL_STOPWORDS = {
    "crl",
    "crl.a",
    "magistrate",
    "wherein",
    "court",
    "state",
    "prosecution",
    "police",
    "judgement",
    "judgment",
    "order",
    "section",
    "act",
    "appellant",
    "respondent",
    "addl",
    "judicature",
    "sessions",
    "high court",
    "supreme court",
    "appellant/",
    "appellant/ accused",
    "appellant(s",
}


def is_valid_person_entity(node_id: str, node_data: dict[str, Any]) -> bool:
    """Validate that a graph node corresponds to an actual human PERSON and not procedural text."""
    entity_type = str(node_data.get("entity_type", "")).upper()
    if entity_type not in {"PERSON", "ACCUSED", "INDIVIDUAL"}:
        return False

    name = str(node_data.get("name", "")).strip()
    if len(name) < 3:
        return False

    name_lower = name.lower()
    if name_lower in PROCEDURAL_STOPWORDS:
        return False

    if re.match(r"^(p\.?w\.?[-0-9]|crl|appellant|respondent)", name_lower):
        return False

    if not is_valid_accused_person(name):
        return False

    return True


def calculate_pagerank(
    G: nx.Graph,
    alpha: float = 0.85,
    max_iter: int = 500,
    weight: str = "weight",
) -> dict[str, float]:
    """Calculate PageRank using SciPy if installed, or NetworkX pure-Python fallback."""
    if len(G) == 0:
        return {}
    try:
        return nx.pagerank(G, alpha=alpha, max_iter=max_iter, weight=weight)
    except (ImportError, ModuleNotFoundError):
        from networkx.algorithms.link_analysis.pagerank_alg import _pagerank_python

        return _pagerank_python(G, alpha=alpha, max_iter=max_iter, weight=weight)
    except Exception as exc:
        logger.warning("Weighted PageRank encountered issue: %s; falling back to unweighted.", exc)
        try:
            return nx.pagerank(G, alpha=alpha, max_iter=max_iter, weight=None)
        except (ImportError, ModuleNotFoundError):
            from networkx.algorithms.link_analysis.pagerank_alg import _pagerank_python

            return _pagerank_python(G, alpha=alpha, max_iter=max_iter, weight=None)


def compute_centrality_metrics(G: nx.Graph) -> dict[str, Any]:
    """Calculate raw degree, degree centrality, betweenness centrality, and PageRank for all nodes.

    Args:
        G: NetworkX Graph loaded from MongoDB.

    Returns:
        dict: Mapping of metric_name -> {node_id: value}
    """
    if len(G) == 0:
        return {
            "degree_centrality": {},
            "raw_degree": {},
            "betweenness_centrality": {},
            "pagerank": {},
        }

    degree_centrality = nx.degree_centrality(G)
    raw_degree = dict(G.degree())
    betweenness_centrality = nx.betweenness_centrality(G, normalized=True)
    pagerank = calculate_pagerank(G, alpha=0.85, max_iter=500, weight="weight")

    return {
        "degree_centrality": degree_centrality,
        "raw_degree": raw_degree,
        "betweenness_centrality": betweenness_centrality,
        "pagerank": pagerank,
    }


def compute_combined_rankings(
    G: nx.Graph,
    metrics: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Compute combined ranking for actual PERSON entities in the graph.

    Ranking formula:
        combined_score = round(0.50 * degree_norm + 0.20 * betweenness_norm + 0.30 * pagerank_norm, 4)

    Rationale:
    - 50% Degree Centrality: Immediate direct criminal co-occurrence or co-accused connectivity.
    - 20% Betweenness Centrality: Brokerage role connecting otherwise disconnected network components.
    - 30% PageRank: Structural prominence based on recursive neighborhood connections.

    Args:
        G: NetworkX graph.
        metrics: Optional precomputed centrality metrics dict.

    Returns:
        List of ranked person dicts sorted deterministically descending by combined score.
    """
    if metrics is None:
        metrics = compute_centrality_metrics(G)

    deg_c = metrics["degree_centrality"]
    raw_d = metrics["raw_degree"]
    bet_c = metrics["betweenness_centrality"]
    pr_c = metrics["pagerank"]

    person_nodes = [
        n for n, d in G.nodes(data=True)
        if is_valid_person_entity(n, d)
    ]

    if not person_nodes:
        return []

    # Min-max normalization strictly over the valid PERSON population
    deg_vals = [deg_c.get(n, 0.0) for n in person_nodes]
    bet_vals = [bet_c.get(n, 0.0) for n in person_nodes]
    pr_vals = [pr_c.get(n, 0.0) for n in person_nodes]

    min_deg, max_deg = min(deg_vals), max(deg_vals)
    min_bet, max_bet = min(bet_vals), max(bet_vals)
    min_pr, max_pr = min(pr_vals), max(pr_vals)

    ranked_items: list[dict[str, Any]] = []

    for n in person_nodes:
        d_raw_val = deg_c.get(n, 0.0)
        b_raw_val = bet_c.get(n, 0.0)
        p_raw_val = pr_c.get(n, 0.0)
        r_deg = raw_d.get(n, 0)

        # Normalization
        d_norm = (
            (d_raw_val - min_deg) / (max_deg - min_deg)
            if max_deg > min_deg
            else (1.0 if d_raw_val > 0 else 0.0)
        )
        b_norm = (
            (b_raw_val - min_bet) / (max_bet - min_bet)
            if max_bet > min_bet
            else (1.0 if b_raw_val > 0 else 0.0)
        )
        p_norm = (
            (p_raw_val - min_pr) / (max_pr - min_pr)
            if max_pr > min_pr
            else (1.0 if p_raw_val > 0 else 0.0)
        )

        combined_score = round(0.50 * d_norm + 0.20 * b_norm + 0.30 * p_norm, 4)
        name = G.nodes[n].get("name") or n

        ranked_items.append({
            "entity_id": n,
            "canonical_name": name,
            "degree": round(d_raw_val, 4),
            "raw_degree": r_deg,
            "betweenness": round(b_raw_val, 4),
            "pagerank": round(p_raw_val, 4),
            "combined_score": combined_score,
            "_d_norm": d_norm,
            "_b_norm": b_norm,
            "_p_norm": p_norm,
        })

    # Deterministic sorting: combined_score desc, raw_degree desc, degree desc, name asc, id asc
    ranked_items.sort(
        key=lambda x: (
            -x["combined_score"],
            -x["raw_degree"],
            -x["degree"],
            x["canonical_name"].lower(),
            x["entity_id"],
        )
    )

    # Assign 1-indexed rank
    for idx, item in enumerate(ranked_items, start=1):
        item["rank"] = idx

    return ranked_items
