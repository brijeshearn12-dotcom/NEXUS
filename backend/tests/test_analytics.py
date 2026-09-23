"""Automated test suite for Task 5.1 — Centrality, Pattern Flags & Reasoning Trail.

Covers:
1. Centrality: Degree, Betweenness, PageRank, deterministic combined ranking
2. Communities: Louvain execution, community membership, tiny graph fallback
3. Flags: Bridge node, cross-case recurrence, density anomaly, no-flag case
4. Reasoning trail: Complete structure (input_refs, evidence, reasoning, result, confidence, source)
5. API: GET /api/cases/{case_id}/analysis including insufficient-data and 404 behavior
"""

from __future__ import annotations

import networkx as nx
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.services.analytics.centrality import (
    compute_centrality_metrics,
    compute_combined_rankings,
)
from app.services.analytics.community import (
    detect_louvain_communities,
)
from app.services.analytics.key_individuals import (
    rank_key_individuals,
)
from app.services.analytics.pattern_flags import (
    detect_pattern_flags,
)

client = TestClient(app)


# ── 1. CENTRALITY TESTS ───────────────────────────────────────────────────────


def test_degree_centrality_calculation():
    G = nx.Graph()
    # Star graph: center has degree 3, leaves have degree 1
    G.add_node("p_center", name="Vikas Yadav", entity_type="PERSON")
    G.add_node("p_1", name="Vishal Yadav", entity_type="PERSON")
    G.add_node("p_2", name="Sukhdev", entity_type="PERSON")
    G.add_node("p_3", name="Mohit", entity_type="PERSON")

    G.add_edge("p_center", "p_1", weight=1.0)
    G.add_edge("p_center", "p_2", weight=1.0)
    G.add_edge("p_center", "p_3", weight=1.0)

    metrics = compute_centrality_metrics(G)
    deg_c = metrics["degree_centrality"]
    raw_d = metrics["raw_degree"]

    assert raw_d["p_center"] == 3
    assert raw_d["p_1"] == 1
    assert deg_c["p_center"] == 1.0
    assert round(deg_c["p_1"], 4) == round(1 / 3, 4)


def test_betweenness_centrality_calculation():
    # Line graph: A - B - C
    G = nx.Graph()
    G.add_node("A", name="Person A", entity_type="PERSON")
    G.add_node("B", name="Person B", entity_type="PERSON")
    G.add_node("C", name="Person C", entity_type="PERSON")

    G.add_edge("A", "B", weight=1.0)
    G.add_edge("B", "C", weight=1.0)

    metrics = compute_centrality_metrics(G)
    bet_c = metrics["betweenness_centrality"]

    # In A - B - C, only B lies on the shortest path between other pairs
    assert bet_c["B"] == 1.0
    assert bet_c["A"] == 0.0
    assert bet_c["C"] == 0.0


def test_pagerank_calculation():
    G = nx.cycle_graph(5)
    for n in G.nodes():
        G.nodes[n]["name"] = f"Person {n}"
        G.nodes[n]["entity_type"] = "PERSON"

    metrics = compute_centrality_metrics(G)
    pr = metrics["pagerank"]

    assert len(pr) == 5
    # In symmetric cycle, all nodes should receive equal PageRank (1/5 = 0.2)
    for n in G.nodes():
        assert abs(pr[n] - 0.20) < 0.01
    assert abs(sum(pr.values()) - 1.0) < 0.01


def test_deterministic_combined_ranking_and_person_filtering():
    G = nx.Graph()
    # Person entities
    G.add_node("p_high", name="Key Person 1", entity_type="PERSON")
    G.add_node("p_mid", name="Key Person 2", entity_type="PERSON")
    G.add_node("p_low", name="Key Person 3", entity_type="PERSON")
    # Non-person entities (should be excluded from ranking)
    G.add_node("org_1", name="Crime Syndicate Ltd", entity_type="ORGANIZATION")
    G.add_node("loc_1", name="Connaught Place", entity_type="LOCATION")
    G.add_node("legal_role", name="Public Prosecutor", entity_type="PERSON")

    G.add_edge("p_high", "p_mid", weight=2.0)
    G.add_edge("p_high", "p_low", weight=1.0)
    G.add_edge("p_high", "org_1", weight=1.0)
    G.add_edge("p_high", "loc_1", weight=1.0)
    G.add_edge("p_mid", "loc_1", weight=1.0)

    ranked = compute_combined_rankings(G)

    # Only valid PERSON entities should be ranked
    ranked_ids = [r["entity_id"] for r in ranked]
    assert "p_high" in ranked_ids
    assert "p_mid" in ranked_ids
    assert "p_low" in ranked_ids
    assert "org_1" not in ranked_ids
    assert "loc_1" not in ranked_ids
    assert "legal_role" not in ranked_ids

    # p_high has highest degree and connections
    assert ranked[0]["entity_id"] == "p_high"
    assert ranked[0]["rank"] == 1
    assert ranked[0]["combined_score"] >= ranked[1]["combined_score"]

    # Verify deterministic tie-breaking by running twice
    ranked_second_run = compute_combined_rankings(G)
    assert [r["entity_id"] for r in ranked] == [r["entity_id"] for r in ranked_second_run]


# ── 2. COMMUNITY DETECTION TESTS ─────────────────────────────────────────────


def test_louvain_execution_and_membership():
    # Build two distinct cliques joined by a single bridge edge
    G = nx.Graph()
    # Clique 1: 1, 2, 3
    for i in [1, 2, 3]:
        G.add_node(f"c1_{i}", name=f"Member 1-{i}", entity_type="PERSON")
    G.add_edge("c1_1", "c1_2", weight=1.0)
    G.add_edge("c1_2", "c1_3", weight=1.0)
    G.add_edge("c1_1", "c1_3", weight=1.0)

    # Clique 2: 4, 5, 6
    for i in [4, 5, 6]:
        G.add_node(f"c2_{i}", name=f"Member 2-{i}", entity_type="PERSON")
    G.add_edge("c2_4", "c2_5", weight=1.0)
    G.add_edge("c2_5", "c2_6", weight=1.0)
    G.add_edge("c2_4", "c2_6", weight=1.0)

    # Bridge edge
    G.add_edge("c1_3", "c2_4", weight=0.5)

    comms = detect_louvain_communities(G)
    assert len(comms) >= 2
    for c in comms:
        assert "community_id" in c
        assert "member_ids" in c
        assert "member_names" in c
        assert "size" in c
        assert c["size"] == len(c["member_ids"])
        assert len(c["member_names"]) == len(c["member_ids"])


def test_louvain_tiny_graph_fallback():
    # Graph with 2 nodes and 1 edge (below minimum threshold)
    G = nx.Graph()
    G.add_node("n1", name="Person 1", entity_type="PERSON")
    G.add_node("n2", name="Person 2", entity_type="PERSON")
    G.add_edge("n1", "n2", weight=1.0)

    comms = detect_louvain_communities(G)
    assert comms == []


# ── 3. PATTERN FLAGS TESTS ───────────────────────────────────────────────────


def test_flag_bridge_node():
    # Two cliques connected exclusively through one bridge individual B
    # Clique 1: A1 - A2 - B
    # Clique 2: B - C1 - C2
    G = nx.Graph()
    for n in ["A1", "A2", "B", "C1", "C2"]:
        G.add_node(n, name=f"Individual {n}", entity_type="PERSON")

    G.add_edge("A1", "A2", weight=1.0, edge_id="e_a1_a2", evidence="Met together")
    G.add_edge("A1", "B", weight=1.0, edge_id="e_a1_b", evidence="A1 contacted B")
    G.add_edge("A2", "B", weight=1.0, edge_id="e_a2_b", evidence="A2 conspired with B")

    G.add_edge("B", "C1", weight=1.0, edge_id="e_b_c1", evidence="B instructed C1")
    G.add_edge("B", "C2", weight=1.0, edge_id="e_b_c2", evidence="B financed C2")
    G.add_edge("C1", "C2", weight=1.0, edge_id="e_c1_c2", evidence="C1 met C2")

    flags = detect_pattern_flags(G, case_id="case_flag_test", database=None)
    bridge_flags = [f for f in flags if f["flag_type"] == "bridge_node"]

    assert len(bridge_flags) >= 1
    flag_nodes = [f["entity_id"] for f in bridge_flags]
    assert "B" in flag_nodes

    b_flag = next(f for f in bridge_flags if f["entity_id"] == "B")
    assert b_flag["severity"] == "high"
    assert "articulation" in b_flag["trail"]["reasoning"][0].lower()


def test_flag_density_anomaly():
    # Large sparse path with one extremely dense clique of 4 nodes
    G = nx.path_graph(15)
    for n in G.nodes():
        G.nodes[n]["name"] = f"Person {n}"
        G.nodes[n]["entity_type"] = "PERSON"

    # Turn nodes 0, 1, 2, 3 into a complete 4-clique (clustering coeff = 1.0)
    clique_nodes = [0, 1, 2, 3]
    for i in range(len(clique_nodes)):
        for j in range(i + 1, len(clique_nodes)):
            G.add_edge(clique_nodes[i], clique_nodes[j], weight=1.0, edge_id=f"e_{i}_{j}")

    flags = detect_pattern_flags(G, case_id="case_density_test", database=None)
    density_flags = [f for f in flags if f["flag_type"] == "density_anomaly"]

    assert len(density_flags) >= 1
    # Dense clique nodes should be flagged
    flagged_ids = [f["entity_id"] for f in density_flags]
    assert any(n in flagged_ids for n in clique_nodes)


def test_flag_cross_case_recurrence():
    G = nx.Graph()
    G.add_node("p_cross", name="Cross Case Individual", entity_type="PERSON")
    G.add_node("p_local", name="Local Person", entity_type="PERSON")
    G.add_node("p_other", name="Other Person", entity_type="PERSON")

    # Add edges with multiple case_ids to simulate cross-case occurrence
    G.add_edge(
        "p_cross",
        "p_local",
        weight=1.0,
        edge_id="e_cross_1",
        case_ids=["case_101", "case_202"],
        evidence="Observed in both cases",
    )
    G.add_edge(
        "p_local",
        "p_other",
        weight=1.0,
        edge_id="e_cross_2",
        case_ids=["case_101"],
        evidence="Single case mention",
    )

    flags = detect_pattern_flags(G, case_id="case_101", database=None)
    cross_flags = [f for f in flags if f["flag_type"] == "cross_case_recurrence"]

    assert len(cross_flags) >= 1
    assert cross_flags[0]["entity_id"] == "p_cross"
    assert "case_101" in cross_flags[0]["trail"]["result"]["cases"]
    assert "case_202" in cross_flags[0]["trail"]["result"]["cases"]


def test_no_flag_case():
    # Complete graph K5: all nodes connected directly, betweenness is exactly 0.0,
    # global density is 1.0, local clustering is 1.0 (no density anomaly ratio),
    # no articulation points.
    G_clique = nx.complete_graph(5)
    G = nx.Graph()
    for n in G_clique.nodes():
        node_id = f"person_{n}"
        G.add_node(node_id, name=f"Individual {n}", entity_type="PERSON")
    for u, v in G_clique.edges():
        u_id = f"person_{u}"
        v_id = f"person_{v}"
        G.add_edge(u_id, v_id, weight=1.0, edge_id=f"e_{u}_{v}", case_ids=["case_no_flag"])

    flags = detect_pattern_flags(G, case_id="case_no_flag", database=None)
    assert len(flags) == 0


# ── 4. REASONING TRAIL STRUCTURE TESTS ───────────────────────────────────────


def test_reasoning_trail_completeness_on_ranked_and_flags():
    G = nx.Graph()
    G.add_node("p1", name="Target Individual", entity_type="PERSON", evidence_snippet="A-1 was present")
    G.add_node("p2", name="Accomplice", entity_type="PERSON")
    G.add_node("p3", name="Contact", entity_type="PERSON")

    G.add_edge(
        "p1",
        "p2",
        weight=1.5,
        edge_id="e_p1_p2",
        evidence="Conspired together at safehouse",
        document_ids=["doc_101"],
        provenance={"confidence": 0.95},
    )
    G.add_edge(
        "p1",
        "p3",
        weight=1.0,
        edge_id="e_p1_p3",
        evidence="Called on mobile phone",
        document_ids=["doc_101"],
        provenance={"confidence": 0.90},
    )
    G.add_edge("p2", "p3", weight=1.0, edge_id="e_p2_p3")

    ranked = rank_key_individuals(G, case_id="case_test_trail")
    assert len(ranked) >= 1

    for individual in ranked:
        trail = individual["trail"]
        assert "input_refs" in trail
        assert isinstance(trail["input_refs"], list)
        assert len(trail["input_refs"]) > 0

        assert "evidence" in trail
        assert isinstance(trail["evidence"], list)

        assert "reasoning" in trail
        assert isinstance(trail["reasoning"], list)
        assert len(trail["reasoning"]) >= 3
        # Check deterministic formula explanation exists
        assert any("combined score" in r.lower() for r in trail["reasoning"])

        assert "result" in trail
        assert "rank" in trail["result"]
        assert "combined_score" in trail["result"]

        assert "confidence" in trail
        assert 0.0 <= trail["confidence"] <= 1.0

        assert "source" in trail
        assert isinstance(trail["source"], list)

        # Verify neutral terminology
        assert "role_description" in individual
        assert individual["role_description"] == "key individual based on network metrics"
        assert "mastermind" not in individual["role_description"].lower()
        assert "leader" not in individual["role_description"].lower()


# ── 5. API ENDPOINT TESTS ─────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def clean_test_api_case():
    db = get_db()
    test_case_id = "case_analytics_api_test_51"
    yield
    db.cases.delete_many({"case_id": test_case_id})
    db.documents.delete_many({"case_id": test_case_id})
    db.entities.delete_many({"case_id": test_case_id})
    db.edges.delete_many({"case_ids": test_case_id})
    db.flags.delete_many({"case_id": test_case_id})


def test_api_case_analysis_success():
    db = get_db()
    case_id = "case_analytics_api_test_51"

    db.cases.insert_one({"case_id": case_id, "title": "State v. Syndicate Test"})
    doc_id = "doc_api_test_51"

    # Insert 3 persons and edges
    db.entities.insert_many([
        {
            "id": f"ent_{case_id}_1",
            "name": "Suresh Kumar",
            "entity_type": "PERSON",
            "case_id": case_id,
            "document_id": doc_id,
            "metadata": {"is_accused": True},
        },
        {
            "id": f"ent_{case_id}_2",
            "name": "Ramesh Kumar",
            "entity_type": "PERSON",
            "case_id": case_id,
            "document_id": doc_id,
            "metadata": {"is_accused": True},
        },
        {
            "id": f"ent_{case_id}_3",
            "name": "Dinesh Kumar",
            "entity_type": "PERSON",
            "case_id": case_id,
            "document_id": doc_id,
            "metadata": {"is_accused": True},
        },
    ])

    db.edges.insert_many([
        {
            "edge_id": f"edge_{case_id}_1",
            "source_entity_id": f"ent_{case_id}_1",
            "target_entity_id": f"ent_{case_id}_2",
            "edge_type": "co_accused",
            "weight": 1.5,
            "case_id": case_id,
            "case_ids": [case_id],
            "document_ids": [doc_id],
            "evidence": "Suresh Kumar and Ramesh Kumar acted jointly",
        },
        {
            "edge_id": f"edge_{case_id}_2",
            "source_entity_id": f"ent_{case_id}_1",
            "target_entity_id": f"ent_{case_id}_3",
            "edge_type": "associated_with",
            "weight": 1.0,
            "case_id": case_id,
            "case_ids": [case_id],
            "document_ids": [doc_id],
            "evidence": "Suresh met Dinesh at railway station",
        },
    ])

    resp = client.get(f"/api/cases/{case_id}/analysis")
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "ok"
    assert data["case_id"] == case_id
    assert len(data["ranked_individuals"]) == 3
    assert data["ranked_individuals"][0]["rank"] == 1
    # Suresh Kumar connects both Ramesh and Dinesh, so rank 1
    assert data["ranked_individuals"][0]["canonical_name"] == "Suresh Kumar"
    assert len(data["communities"]) >= 1
    assert "trail" in data
    assert "legal_notice" in data["trail"]

    # Verify idempotency by calling again
    resp2 = client.get(f"/api/cases/{case_id}/analysis")
    assert resp2.status_code == 200
    assert resp2.json()["ranked_individuals"][0]["entity_id"] == data["ranked_individuals"][0]["entity_id"]


def test_api_case_analysis_insufficient_data():
    db = get_db()
    case_id = "case_analytics_api_test_51"

    # Only 1 entity and 0 edges
    db.cases.insert_one({"case_id": case_id, "title": "Tiny Case Test"})
    db.entities.insert_one({
        "id": f"ent_{case_id}_solo",
        "name": "Solo Person",
        "entity_type": "PERSON",
        "case_id": case_id,
    })

    resp = client.get(f"/api/cases/{case_id}/analysis")
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "insufficient_data"
    assert data["case_id"] == case_id
    assert "reason" in data
    assert data["ranked_individuals"] == []
    assert data["communities"] == []
    assert data["flags"] == []


def test_api_case_analysis_not_found():
    resp = client.get("/api/cases/case_nonexistent_xyz_9999/analysis")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()
