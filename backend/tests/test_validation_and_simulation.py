"""Automated test suite for Task 5.2 — Noordin Validation Harness & What-If Simulation.

Covers:
1. Validation Harness:
   - Noordin loader reading 4 category edge CSVs and metadata
   - Graph construction conforming to NEXUS schema (entity_type="PERSON", case_id="noordin_top")
   - Exact reuse of Task 5.1 analytics pipeline (centrality, ranking, Louvain communities)
   - Documented ground truth matching and real agreement score calculation
   - GET /api/validate endpoint integration and response schema
2. What-If Simulation:
   - Node exclusion and deterministic recalculation of rankings, communities, and flags
   - Preservation of original stored MongoDB graph (zero DB modification guarantee)
   - Invalid case ID 404 behavior
   - Unknown node exclusion resilience
   - Empty exclusion list idempotency
   - Tiny/empty resulting graph insufficient_data fallback
   - POST /api/cases/{case_id}/simulate endpoint integration
"""

from __future__ import annotations

import networkx as nx
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.services.analytics.centrality import (
    compute_centrality_metrics,
    compute_combined_rankings,
)
from app.services.analytics.community import detect_louvain_communities
from app.services.analytics.key_individuals import rank_key_individuals
from app.services.graph.networkx_loader import load_case_graph
from app.services.validation.noordin_loader import (
    build_noordin_graph,
    load_all_noordin_edges,
    load_noordin_metadata,
    run_noordin_validation,
)

client = TestClient(app)

TEST_REAL_CASE_ID = "case_100478559"


# ── 1. NOORDIN VALIDATION HARNESS TESTS ─────────────────────────────────────────


def test_noordin_loader_reads_datasets():
    """Verify that all categorized edge files and metadata are present and read correctly."""
    edges = load_all_noordin_edges()
    assert "communication" in edges
    assert "operational" in edges
    assert "trust" in edges
    assert "financial" in edges

    assert len(edges["communication"]) > 0
    assert len(edges["operational"]) > 0
    assert len(edges["trust"]) > 0
    # Financial edges file is documented as 0 rows (no pairwise transactions fabricated)
    assert len(edges["financial"]) == 0

    metadata = load_noordin_metadata()
    assert "dataset_name" in metadata
    assert "benchmark_metrics" in metadata
    assert "key_actors" in metadata["benchmark_metrics"]
    assert len(metadata["benchmark_metrics"]["key_actors"]) == 5


def test_noordin_graph_construction():
    """Verify that the Noordin validation graph normalizes into the standard NEXUS graph schema."""
    G = build_noordin_graph()

    assert isinstance(G, nx.Graph)
    assert G.number_of_nodes() == 19
    assert G.number_of_edges() == 19

    # Verify nodes have required NEXUS attributes for analytics compatibility
    for node_id, data in G.nodes(data=True):
        assert data.get("name") == node_id
        assert data.get("entity_type") == "PERSON"
        assert data.get("verification_status") == "verified"
        assert data.get("case_id") == "noordin_top"

    # Verify edges have required attributes
    for _u, _v, data in G.edges(data=True):
        assert "weight" in data
        assert data["weight"] >= 1.0
        assert "edge_type" in data
        assert "relationship" in data


def test_noordin_identical_analytics_pipeline():
    """Verify that the exact Task 5.1 analytics functions run directly on the Noordin graph."""
    G = build_noordin_graph()

    # 1. Centrality metrics
    metrics = compute_centrality_metrics(G)
    assert "degree_centrality" in metrics
    assert "betweenness_centrality" in metrics
    assert "pagerank" in metrics

    # Noordin Mohammad Top must have highest degree in the network
    deg = metrics["raw_degree"]
    assert deg["Noordin Mohammad Top"] == max(deg.values())

    # 2. Combined rankings
    rankings = compute_combined_rankings(G, metrics=metrics)
    assert len(rankings) == 19
    assert rankings[0]["canonical_name"] == "Noordin Mohammad Top"
    assert rankings[0]["combined_score"] == 1.0

    # 3. Louvain communities
    communities = detect_louvain_communities(G)
    assert len(communities) >= 2
    for comm in communities:
        assert comm["size"] >= 2
        assert len(comm["member_ids"]) == comm["size"]

    # 4. Key individuals with reasoning trail
    key_inds = rank_key_individuals(G, case_id="noordin_top", communities=communities)
    assert len(key_inds) == 19
    first = key_inds[0]
    assert first["canonical_name"] == "Noordin Mohammad Top"
    assert "trail" in first
    assert "input_refs" in first["trail"]
    assert "reasoning" in first["trail"]
    assert "confidence" in first["trail"]


def test_noordin_ground_truth_matching_and_real_score():
    """Verify ground-truth figure matching and honest validation score calculation."""
    res = run_noordin_validation(top_k=5)

    assert res["status"] == "ok"
    assert res["ground_truth_count"] == 5
    assert res["top_k"] == 5
    assert res["matches"] == 4
    assert res["score"] == "4 of top 5 match documented figures"
    assert res["score_percentage"] == 80.0

    # Documented matched figures
    matched_names = [m["name"] for m in res["matching_figures"]]
    assert "Noordin Mohammad Top" in matched_names
    assert "Azahari Husin" in matched_names
    assert "Urwah" in matched_names
    assert "Irun Ali" in matched_names

    # Documented unmatched figure in top 5
    unmatched_names = [u["name"] for u in res["unmatched_ground_truth"]]
    assert "Fathur Rahman al-Ghozi" in unmatched_names

    # Verify legal notice
    assert "legal_notice" in res
    assert "does not establish legal guilt" in res["legal_notice"]


def test_api_validate_endpoint():
    """Verify GET /api/validate endpoint response and parameter handling."""
    resp = client.get("/api/validate")
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "ok"
    assert "dataset" in data
    assert "source_reference" in data
    assert "ground_truth_figures" in data
    assert "score" in data
    assert data["matches"] == 4

    # Test custom top_k parameter
    resp_k10 = client.get("/api/validate?top_k=10")
    assert resp_k10.status_code == 200
    data_k10 = resp_k10.json()
    assert data_k10["top_k"] == 10
    # In top 10, all 5 documented key actors appear
    assert data_k10["matches"] == 5


# ── 2. WHAT-IF SIMULATION TESTS ───────────────────────────────────────────────


def test_simulation_node_exclusion_and_ranking_change():
    """Verify that excluding a central node in what-if simulation visibly recalculates rankings."""
    resp_orig = client.get(f"/api/cases/{TEST_REAL_CASE_ID}/analysis")
    assert resp_orig.status_code == 200
    orig_data = resp_orig.json()
    assert orig_data["status"] == "ok"
    assert len(orig_data["ranked_individuals"]) > 0

    top_node_id = orig_data["ranked_individuals"][0]["entity_id"]
    top_node_name = orig_data["ranked_individuals"][0]["canonical_name"]

    # Run simulation excluding top central node
    resp_sim = client.post(
        f"/api/cases/{TEST_REAL_CASE_ID}/simulate",
        json={"exclude_node_ids": [top_node_id]},
    )
    assert resp_sim.status_code == 200
    sim_data = resp_sim.json()

    assert sim_data["status"] == "ok"
    assert sim_data["changed"] is True
    assert top_node_id in sim_data["actually_removed_node_ids"]
    assert sim_data["impact_summary"]["removed_nodes_count"] == 1

    # Verify excluded node is absent from simulated top individuals
    sim_ids = [ind["entity_id"] for ind in sim_data["simulated_top_individuals"]]
    assert top_node_id not in sim_ids

    # Verify rankings shifted
    sim_new_top = sim_data["simulated_top_individuals"][0]["canonical_name"]
    assert sim_new_top != top_node_name


def test_simulation_preserves_stored_mongodb_graph():
    """Verify the strict guarantee that simulation never modifies the stored MongoDB database."""
    db = get_db()
    orig_edges_count = db.edges.count_documents({"case_id": TEST_REAL_CASE_ID})
    orig_entities_count = db.entities.count_documents({"case_id": TEST_REAL_CASE_ID})

    # Pick a node to exclude
    G_before = load_case_graph(TEST_REAL_CASE_ID, database=db)
    node_to_exclude = list(G_before.nodes())[0]

    # Run simulation
    resp = client.post(
        f"/api/cases/{TEST_REAL_CASE_ID}/simulate",
        json={"exclude_node_ids": [node_to_exclude]},
    )
    assert resp.status_code == 200

    # Verify MongoDB collections remain unchanged
    after_edges_count = db.edges.count_documents({"case_id": TEST_REAL_CASE_ID})
    after_entities_count = db.entities.count_documents({"case_id": TEST_REAL_CASE_ID})
    assert orig_edges_count == after_edges_count
    assert orig_entities_count == after_entities_count

    # Verify reloading the graph from DB still contains the excluded node
    G_after = load_case_graph(TEST_REAL_CASE_ID, database=db)
    assert G_after.has_node(node_to_exclude)
    assert G_after.number_of_nodes() == G_before.number_of_nodes()
    assert G_after.number_of_edges() == G_before.number_of_edges()


def test_simulation_invalid_case_id():
    """Verify that simulating an invalid/nonexistent case ID returns HTTP 404."""
    resp = client.post(
        "/api/cases/nonexistent_case_random_9999/simulate",
        json={"exclude_node_ids": ["ent_some_node"]},
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_simulation_unknown_node_handling():
    """Verify that excluding an unknown or nonexistent node ID does not crash and marks changed=False."""
    resp = client.post(
        f"/api/cases/{TEST_REAL_CASE_ID}/simulate",
        json={"exclude_node_ids": ["ghost_node_that_does_not_exist_in_graph"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["changed"] is False
    assert "ghost_node_that_does_not_exist_in_graph" in data["unknown_node_ids"]
    assert len(data["actually_removed_node_ids"]) == 0


def test_simulation_empty_exclusion_list():
    """Verify that an empty exclusion list returns the baseline ranking with changed=False."""
    resp = client.post(
        f"/api/cases/{TEST_REAL_CASE_ID}/simulate",
        json={"exclude_node_ids": []},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["changed"] is False
    assert len(data["actually_removed_node_ids"]) == 0
    assert len(data["original_top_individuals"]) == len(data["simulated_top_individuals"])


def test_simulation_tiny_graph_fallback():
    """Verify that excluding all or too many nodes triggers the insufficient_data fallback gracefully."""
    G = load_case_graph(TEST_REAL_CASE_ID)
    all_nodes = list(G.nodes())

    resp = client.post(
        f"/api/cases/{TEST_REAL_CASE_ID}/simulate",
        json={"exclude_node_ids": all_nodes},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "insufficient_data"
    assert "remaining after exclusion" in data["reason"]
    assert data["simulated_top_individuals"] == []
