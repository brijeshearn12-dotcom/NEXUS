"""Unit and integration tests for Task 4.2 — Relationship Graph Builder.

Tests:
1. Person-Person co-accused rule
2. Person-Person same-sentence co-occurrence
3. Person-Organization explicit link
4. Person-Location explicit link
5. Person-Vehicle explicit link
6. Legal role filtering (counsel/judges excluded from accused/graph edges)
7. Canonical alias handling (merges mapped to canonical ID)
8. Cross-case linking (canonical entity linking multiple cases)
9. Duplicate edge prevention and deterministic weight aggregation
10. Provenance preservation on edges
11. NetworkX in-memory graph loader
12. API endpoints: POST /api/cases/{case_id}/build-graph and GET /api/cases/{case_id}/graph
"""

from __future__ import annotations

import uuid

import networkx as nx
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.models.enums import ProvenanceMethod, VerificationStatus
from app.services.graph.builder import (
    build_graph_for_case,
    generate_stable_edge_id,
)
from app.services.graph.cross_case_linker import (
    find_cross_case_canonical_entities,
)
from app.services.graph.edge_rules import (
    extract_candidate_edges_from_document,
    is_valid_accused_person,
)
from app.services.graph.networkx_loader import load_case_graph

client = TestClient(app)


# ── 1. RULE TESTS: EXTRACT CANDIDATE EDGES ───────────────────────────────────


def test_co_accused_edge_rule():
    doc_id = "doc_test_1"
    case_id = "case_test_1"
    text = "The prosecution alleged that both individuals engaged in criminal conspiracy."
    entities = [
        {
            "id": "ent_p1",
            "name": "Vikas Yadav",
            "entity_type": "PERSON",
            "metadata": {"is_accused": True},
            "aliases": [],
        },
        {
            "id": "ent_p2",
            "name": "Vishal Yadav",
            "entity_type": "PERSON",
            "metadata": {"is_accused": True},
            "aliases": [],
        },
    ]
    alias_map: dict[str, str] = {}

    candidates = extract_candidate_edges_from_document(
        doc_id=doc_id,
        case_id=case_id,
        text=text,
        entities=entities,
        alias_map=alias_map,
    )

    co_accused = [c for c in candidates if c["edge_type"] == "co_accused"]
    assert len(co_accused) == 1
    edge = co_accused[0]
    assert edge["source_entity_id"] == "ent_p1"
    assert edge["target_entity_id"] == "ent_p2"
    assert "Co-accused in case case_test_1: Vikas Yadav and Vishal Yadav" in edge["evidence_snippet"]
    assert edge["method"] == ProvenanceMethod.ACCUSED_PATTERN.value


def test_person_person_same_sentence_rule():
    doc_id = "doc_test_2"
    case_id = "case_test_2"
    text = "On the night of the incident, Rajesh Sharma met Vikram Singh at the warehouse."
    entities = [
        {
            "id": "ent_rs",
            "name": "Rajesh Sharma",
            "entity_type": "PERSON",
            "metadata": {"is_accused": False},
            "aliases": [],
        },
        {
            "id": "ent_vs",
            "name": "Vikram Singh",
            "entity_type": "PERSON",
            "metadata": {"is_accused": False},
            "aliases": [],
        },
    ]

    candidates = extract_candidate_edges_from_document(
        doc_id=doc_id,
        case_id=case_id,
        text=text,
        entities=entities,
        alias_map={},
    )

    assoc = [c for c in candidates if c["edge_type"] == "associated_with"]
    assert len(assoc) == 1
    edge = assoc[0]
    assert edge["source_entity_id"] == "ent_rs"
    assert edge["target_entity_id"] == "ent_vs"
    assert "Rajesh Sharma met Vikram Singh" in edge["evidence_snippet"]


def test_person_organization_rule():
    doc_id = "doc_test_3"
    case_id = "case_test_3"
    text = "The accused Mohammad Tariq operated under the direct instructions of Lashkar-e-Taiba."
    entities = [
        {
            "id": "ent_tariq",
            "name": "Mohammad Tariq",
            "entity_type": "PERSON",
            "metadata": {"is_accused": True},
            "aliases": [],
        },
        {
            "id": "ent_let",
            "name": "Lashkar-e-Taiba",
            "entity_type": "ORGANIZATION",
            "metadata": {},
            "aliases": [],
        },
    ]

    candidates = extract_candidate_edges_from_document(
        doc_id=doc_id,
        case_id=case_id,
        text=text,
        entities=entities,
        alias_map={},
    )

    assoc = [c for c in candidates if c["edge_type"] == "associated_with"]
    assert len(assoc) == 1
    edge = assoc[0]
    assert edge["source_entity_id"] == "ent_let"
    assert edge["target_entity_id"] == "ent_tariq"
    assert "Mohammad Tariq operated under the direct instructions of Lashkar-e-Taiba" in edge["evidence_snippet"]


def test_person_location_rule():
    doc_id = "doc_test_4"
    case_id = "case_test_4"
    text = "Witness testified that Suresh Kumar was apprehended in Connaught Place on Friday."
    entities = [
        {
            "id": "ent_sk",
            "name": "Suresh Kumar",
            "entity_type": "PERSON",
            "metadata": {"is_accused": True},
            "aliases": [],
        },
        {
            "id": "ent_cp",
            "name": "Connaught Place",
            "entity_type": "LOCATION",
            "metadata": {},
            "aliases": [],
        },
    ]

    candidates = extract_candidate_edges_from_document(
        doc_id=doc_id,
        case_id=case_id,
        text=text,
        entities=entities,
        alias_map={},
    )

    loc_edges = [c for c in candidates if c["edge_type"] == "located_at"]
    assert len(loc_edges) == 1
    assert loc_edges[0]["source_entity_id"] == "ent_cp"
    assert loc_edges[0]["target_entity_id"] == "ent_sk"


def test_person_vehicle_rule():
    doc_id = "doc_test_5"
    case_id = "case_test_5"
    text = "The driver Ramesh Chand fled the crime scene driving DL1CA1234 towards the border."
    entities = [
        {
            "id": "ent_rc",
            "name": "Ramesh Chand",
            "entity_type": "PERSON",
            "metadata": {"is_accused": True},
            "aliases": [],
        },
        {
            "id": "ent_veh",
            "name": "DL1CA1234",
            "entity_type": "VEHICLE",
            "metadata": {},
            "aliases": [],
        },
    ]

    candidates = extract_candidate_edges_from_document(
        doc_id=doc_id,
        case_id=case_id,
        text=text,
        entities=entities,
        alias_map={},
    )

    veh_edges = [c for c in candidates if c["edge_type"] == "used_vehicle"]
    assert len(veh_edges) == 1
    assert veh_edges[0]["source_entity_id"] == "ent_rc"
    assert veh_edges[0]["target_entity_id"] == "ent_veh"


def test_legal_roles_filtered_from_accused_and_edges():
    assert not is_valid_accused_person("Additional Public Prosecutor")
    assert not is_valid_accused_person("Learned Senior Counsel")
    assert not is_valid_accused_person("High Court")
    assert not is_valid_accused_person("Crl.A.No. 450")
    assert is_valid_accused_person("Vikas Yadav")
    assert is_valid_accused_person("Mohammad Tariq")

    doc_id = "doc_test_6"
    case_id = "case_test_6"
    text = "Learned Additional Public Prosecutor argued that Vikas Yadav committed murder."
    entities = [
        {
            "id": "ent_app",
            "name": "Additional Public Prosecutor",
            "entity_type": "PERSON",
            "metadata": {"is_accused": True},
            "aliases": [],
        },
        {
            "id": "ent_vy",
            "name": "Vikas Yadav",
            "entity_type": "PERSON",
            "metadata": {"is_accused": True},
            "aliases": [],
        },
    ]

    candidates = extract_candidate_edges_from_document(
        doc_id=doc_id,
        case_id=case_id,
        text=text,
        entities=entities,
        alias_map={},
    )

    # Should not produce co_accused edge between prosecutor and accused
    assert len(candidates) == 0


# ── 2. CANONICAL ALIAS & CROSS-CASE RESOLUTION ──────────────────────────────


def test_canonical_alias_mapping_in_edges():
    doc_id = "doc_test_7"
    case_id = "case_test_7"
    text = "Vikas and Vishal met at the outskirts."
    entities = [
        {
            "id": "ent_vikas_alias",
            "name": "Vikas",
            "entity_type": "PERSON",
            "metadata": {"is_accused": False},
            "aliases": [],
        },
        {
            "id": "ent_vishal_canon",
            "name": "Vishal",
            "entity_type": "PERSON",
            "metadata": {"is_accused": False},
            "aliases": [],
        },
    ]
    alias_map = {"ent_vikas_alias": "ent_vikas_canon"}

    candidates = extract_candidate_edges_from_document(
        doc_id=doc_id,
        case_id=case_id,
        text=text,
        entities=entities,
        alias_map=alias_map,
    )

    assoc = [c for c in candidates if c["edge_type"] == "associated_with"]
    assert len(assoc) == 1
    # Both endpoints should reflect canonical IDs
    assert assoc[0]["source_entity_id"] == "ent_vikas_canon"
    assert assoc[0]["target_entity_id"] == "ent_vishal_canon"


def test_cross_case_canonical_detection():
    class DummyCol:
        def __init__(self, items):
            self.items = items
        def find(self, *args, **kwargs):
            return list(self.items)

    class DummyDB:
        def __init__(self):
            self.entity_merges = DummyCol([
                {"canonical_entity_id": "ent_canon_1", "alias_entity_id": "ent_alias_1"},
            ])
            self.entities = DummyCol([
                {"id": "ent_canon_1", "case_id": "case_101"},
                {"id": "ent_alias_1", "case_id": "case_202"},
                {"id": "ent_single_case", "case_id": "case_101"},
            ])

    dummy_db = DummyDB()
    cross_map = find_cross_case_canonical_entities(dummy_db)
    assert "ent_canon_1" in cross_map
    assert cross_map["ent_canon_1"] == {"case_101", "case_202"}
    assert "ent_single_case" not in cross_map


# ── 3. DEDUPLICATION AND WEIGHT AGGREGATION ──────────────────────────────────


def test_edge_id_stability():
    id1 = generate_stable_edge_id("ent_a", "ent_b", "associated_with")
    id2 = generate_stable_edge_id("ent_b", "ent_a", "associated_with")
    assert id1 == id2
    assert id1.startswith("edge_")


# ── 4. INTEGRATION TESTS (DB, GRAPH BUILDER & NETWORKX) ──────────────────────


@pytest.fixture(autouse=True)
def clean_test_case_data():
    db = get_db()
    test_case_id = "case_graph_test_suite_42"
    yield
    # Cleanup after test
    db.cases.delete_many({"case_id": test_case_id})
    db.documents.delete_many({"case_id": test_case_id})
    db.entities.delete_many({"case_id": test_case_id})
    db.entity_merges.delete_many({"case_id": test_case_id})
    db.edges.delete_many({"case_ids": test_case_id})
    db.audit_log.delete_many({"details.case_id": test_case_id})


def test_build_graph_for_case_pipeline():
    db = get_db()
    case_id = "case_graph_test_suite_42"
    doc_id = "doc_graph_test_1"

    # Insert test case & document
    db.cases.insert_one({
        "case_id": case_id,
        "title": "State v. Test Network",
        "jurisdiction": "Delhi High Court",
    })

    text = (
        "Accused Vikas Yadav and accused Vishal Yadav conspired together. "
        "Vikas Yadav was seen driving vehicle HR26AB1234 near Connaught Place. "
        "Later, Vikas Yadav met Sukhdev Pehalwan in Connaught Place."
    )
    db.documents.insert_one({
        "document_id": doc_id,
        "case_id": case_id,
        "judgment_text": text,
        "title": "Test Judgment",
    })

    # Insert entities
    e1 = {
        "id": f"ent_{case_id}_1",
        "name": "Vikas Yadav",
        "entity_type": "PERSON",
        "case_id": case_id,
        "document_id": doc_id,
        "metadata": {"is_accused": True},
        "aliases": ["Vikas"],
        "verification_status": VerificationStatus.UNVERIFIED.value,
    }
    e2 = {
        "id": f"ent_{case_id}_2",
        "name": "Vishal Yadav",
        "entity_type": "PERSON",
        "case_id": case_id,
        "document_id": doc_id,
        "metadata": {"is_accused": True},
        "aliases": [],
        "verification_status": VerificationStatus.UNVERIFIED.value,
    }
    e3 = {
        "id": f"ent_{case_id}_3",
        "name": "Sukhdev Pehalwan",
        "entity_type": "PERSON",
        "case_id": case_id,
        "document_id": doc_id,
        "metadata": {"is_accused": True},
        "aliases": [],
        "verification_status": VerificationStatus.UNVERIFIED.value,
    }
    e4 = {
        "id": f"ent_{case_id}_4",
        "name": "HR26AB1234",
        "entity_type": "VEHICLE",
        "case_id": case_id,
        "document_id": doc_id,
        "metadata": {},
        "aliases": [],
        "verification_status": VerificationStatus.UNVERIFIED.value,
    }
    e5 = {
        "id": f"ent_{case_id}_5",
        "name": "Connaught Place",
        "entity_type": "LOCATION",
        "case_id": case_id,
        "document_id": doc_id,
        "metadata": {},
        "aliases": [],
        "verification_status": VerificationStatus.UNVERIFIED.value,
    }

    db.entities.insert_many([e1, e2, e3, e4, e5])

    # Insert a merge record to test canonical entity alias resolution
    e_alias = {
        "id": f"ent_{case_id}_alias",
        "name": "Vikas",
        "entity_type": "PERSON",
        "case_id": case_id,
        "document_id": doc_id,
        "metadata": {},
        "aliases": [],
        "verification_status": VerificationStatus.UNVERIFIED.value,
    }
    db.entities.insert_one(e_alias)
    db.entity_merges.insert_one({
        "merge_id": f"merge_{uuid.uuid4().hex[:8]}",
        "canonical_entity_id": e1["id"],
        "alias_entity_id": e_alias["id"],
        "case_id": case_id,
        "similarity_score": 95.0,
        "confidence": 0.95,
        "method": "alias_resolver",
        "verification_status": VerificationStatus.UNVERIFIED.value,
        "created_at": "2026-09-23T00:00:00Z",
    })

    # 1. Run build_graph_for_case
    result = build_graph_for_case(case_id=case_id, database=db)
    assert result["case_id"] == case_id
    assert result["nodes"] >= 5
    assert result["edges_created"] > 0
    assert result["edges_updated"] == 0

    # 2. Re-run to test idempotency and update behavior
    result2 = build_graph_for_case(case_id=case_id, database=db)
    assert result2["edges_created"] == 0
    assert result2["edges_updated"] == result["edges_created"]

    # 3. Verify edges in DB
    db_edges = list(db.edges.find({"case_ids": case_id}))
    assert len(db_edges) == result["edges_created"]
    for edge in db_edges:
        assert "edge_id" in edge
        assert "source_entity_id" in edge
        assert "target_entity_id" in edge
        assert "edge_type" in edge
        assert "weight" in edge
        assert edge["weight"] >= 0.5
        assert "provenance" in edge
        assert doc_id in edge["document_ids"]
        assert "evidence_snippets" in edge["provenance"]["metadata"]
        assert edge["verification_status"] == VerificationStatus.UNVERIFIED.value

    # Verify NetworkX loader
    G = load_case_graph(case_id=case_id, database=db)
    assert isinstance(G, nx.Graph)
    assert G.number_of_nodes() >= 5
    assert 0 < G.number_of_edges() <= len(db_edges)
    # Check node attributes
    for _, data in G.nodes(data=True):
        assert "name" in data
        assert "entity_type" in data
    # Check edge attributes
    for _, _, data in G.edges(data=True):
        assert "edge_type" in data
        assert "weight" in data
        assert "provenance" in data


def test_api_endpoints_build_and_get_graph():
    db = get_db()
    case_id = "case_graph_test_suite_42"
    doc_id = "doc_graph_test_api"

    db.cases.insert_one({"case_id": case_id, "title": "API Test Case"})
    db.documents.insert_one({
        "document_id": doc_id,
        "case_id": case_id,
        "judgment_text": "A-1 Rajesh and A-2 Mohan were arrested in Old Delhi.",
    })
    db.entities.insert_many([
        {
            "id": f"ent_{case_id}_r",
            "name": "Rajesh",
            "entity_type": "PERSON",
            "case_id": case_id,
            "document_id": doc_id,
            "metadata": {"is_accused": True},
            "aliases": [],
        },
        {
            "id": f"ent_{case_id}_m",
            "name": "Mohan",
            "entity_type": "PERSON",
            "case_id": case_id,
            "document_id": doc_id,
            "metadata": {"is_accused": True},
            "aliases": [],
        },
        {
            "id": f"ent_{case_id}_od",
            "name": "Old Delhi",
            "entity_type": "LOCATION",
            "case_id": case_id,
            "document_id": doc_id,
            "metadata": {},
            "aliases": [],
        },
    ])

    # POST build-graph
    resp_post = client.post(f"/api/cases/{case_id}/build-graph")
    assert resp_post.status_code == 200
    data_post = resp_post.json()
    assert data_post["case_id"] == case_id
    assert data_post["nodes"] >= 3
    assert data_post["edges_created"] >= 1

    # GET graph
    resp_get = client.get(f"/api/cases/{case_id}/graph")
    assert resp_get.status_code == 200
    data_get = resp_get.json()
    assert len(data_get["nodes"]) >= 3
    assert len(data_get["edges"]) >= 1

    first_edge = data_get["edges"][0]
    assert "edge_id" in first_edge
    assert "edge_type" in first_edge
    assert "weight" in first_edge
    assert "provenance" in first_edge
    assert "evidence_snippets" in first_edge["provenance"]["metadata"]
