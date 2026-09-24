"""Automated test suite for Task 7.2 — Corpus-Level Command Center endpoints.

Covers:
1. GET /api/corpus/stats
   - Returns HTTP 200 with schema matching CorpusStatsResponse
   - Real MongoDB counts for documents, cases, entities, edges, flags
   - Validation score returned correctly when present ("4/5")
   - Missing validation score handled gracefully as None/null
   - Database failure handled safely with 500 error and safe message (no leaked secrets)
2. GET /api/cases/priority
   - Returns HTTP 200 with schema matching CasePriorityResponse
   - Priority queue contains real cases
   - Validates correct field names (case_id, title, document_count, entity_count, edge_count, flag_count, priority)
   - Priority status logic: Needs Verification, Needs Analysis, Ready, Insufficient Data
   - Database failure handled safely with 500 error
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app

client = TestClient(app)


def test_corpus_stats_endpoint_returns_real_counts():
    """Verify GET /api/corpus/stats returns 200 and matches actual MongoDB collection counts."""
    db = get_db()
    expected_docs = db.documents.count_documents({})
    expected_cases = db.cases.count_documents({})
    expected_entities = db.entities.count_documents({})
    expected_edges = db.edges.count_documents({})
    expected_flags = db.flags.count_documents({})

    resp = client.get("/api/corpus/stats")
    assert resp.status_code == 200
    data = resp.json()

    assert data["documents"] == expected_docs
    assert data["cases"] == expected_cases
    assert data["entities"] == expected_entities
    assert data["edges"] == expected_edges
    assert data["flags"] == expected_flags
    assert "validation_score" in data


def test_corpus_stats_validation_score_handling():
    """Verify validation_score reflects latest validation run or None when absent."""
    # Case A: Validation run exists
    # Trigger /api/validate to ensure at least one run is recorded
    val_resp = client.get("/api/validate")
    assert val_resp.status_code == 200

    resp = client.get("/api/corpus/stats")
    assert resp.status_code == 200
    assert resp.json()["validation_score"] == "4/5"

    # Case B: When no validation run is recorded, returns null
    with patch("app.api.corpus.get_db") as mock_get_db:
        mock_db = MagicMock()
        mock_db.documents.count_documents.return_value = 10
        mock_db.cases.count_documents.return_value = 2
        mock_db.entities.count_documents.return_value = 50
        mock_db.edges.count_documents.return_value = 20
        mock_db.flags.count_documents.return_value = 1
        mock_db.validation_runs.find_one.return_value = None
        mock_get_db.return_value = mock_db

        mock_resp = client.get("/api/corpus/stats")
        assert mock_resp.status_code == 200
        mock_data = mock_resp.json()
        assert mock_data["documents"] == 10
        assert mock_data["validation_score"] is None


def test_corpus_stats_database_failure_handling():
    """Verify database errors in /api/corpus/stats return 500 without leaking secrets or crashing."""
    with patch("app.api.corpus.get_db") as mock_get_db:
        mock_db = MagicMock()
        mock_db.documents.count_documents.side_effect = RuntimeError("Atlas connection failure mongodb+srv://secret")
        mock_get_db.return_value = mock_db

        resp = client.get("/api/corpus/stats")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Unable to load corpus data."
        # Confirm connection string or secret is not exposed in detail
        assert "mongodb" not in resp.text.lower()
        assert "secret" not in resp.text.lower()


def test_cases_priority_endpoint_returns_real_queue():
    """Verify GET /api/cases/priority returns 200 with realistic prioritized cases."""
    resp = client.get("/api/cases/priority")
    assert resp.status_code == 200
    data = resp.json()

    assert "items" in data
    assert "total" in data
    assert data["total"] > 0
    assert len(data["items"]) == data["total"]

    valid_priorities = {"Needs Verification", "Needs Analysis", "Ready", "Insufficient Data"}
    valid_analysis_statuses = {"completed", "unanalysed", "insufficient_data"}
    valid_verification_statuses = {"needs_verification", "verified", "unverified"}

    for item in data["items"]:
        assert "case_id" in item and item["case_id"]
        assert "title" in item
        assert "document_count" in item and item["document_count"] >= 0
        assert "entity_count" in item and item["entity_count"] >= 0
        assert "edge_count" in item and item["edge_count"] >= 0
        assert "flag_count" in item and item["flag_count"] >= 0
        assert item["priority"] in valid_priorities
        assert item["analysis_status"] in valid_analysis_statuses
        assert item["verification_status"] in valid_verification_statuses

    # Verify curated demo case exists and has expected status
    case_ids = [c["case_id"] for c in data["items"]]
    assert "case_100478559" in case_ids
    demo_item = next(c for c in data["items"] if c["case_id"] == "case_100478559")
    assert demo_item["entity_count"] == 225
    assert demo_item["analysis_status"] == "completed"
    assert demo_item["priority"] == "Needs Verification"


def test_cases_priority_logic_scenarios():
    """Verify priority classification logic under controlled mock conditions."""
    with patch("app.api.cases.get_db") as mock_get_db:
        mock_db = MagicMock()
        # Mock aggregations
        mock_db.documents.aggregate.return_value = [
            {"_id": "case_empty", "count": 0},
            {"_id": "case_no_analysis", "count": 2},
            {"_id": "case_unverified", "count": 1},
            {"_id": "case_ready", "count": 3},
        ]
        mock_db.entities.aggregate.return_value = [
            {"_id": "case_empty", "total": 0, "unverified": 0},
            {"_id": "case_no_analysis", "total": 15, "unverified": 15},
            {"_id": "case_unverified", "total": 20, "unverified": 2},
            {"_id": "case_ready", "total": 30, "unverified": 0},
        ]
        mock_db.edges.aggregate.return_value = [
            {"_id": "case_empty", "total": 0},
            {"_id": "case_no_analysis", "total": 0},
            {"_id": "case_unverified", "total": 10},
            {"_id": "case_ready", "total": 25},
        ]
        mock_db.flags.aggregate.return_value = [
            {"_id": "case_unverified", "total": 1, "unverified": 1},
            {"_id": "case_ready", "total": 1, "unverified": 0},
        ]
        # Only case_unverified and case_ready have completed network analysis
        mock_db.audit_log.distinct.return_value = ["case_unverified", "case_ready"]

        mock_db.cases.find.return_value = [
            {"case_id": "case_empty", "title": "Empty Case"},
            {"case_id": "case_no_analysis", "title": "Unanalysed Case"},
            {"case_id": "case_unverified", "title": "Needs Review Case"},
            {"case_id": "case_ready", "title": "Fully Verified Case"},
        ]
        mock_get_db.return_value = mock_db

        resp = client.get("/api/cases/priority")
        assert resp.status_code == 200
        items_map = {item["case_id"]: item for item in resp.json()["items"]}

        assert items_map["case_empty"]["priority"] == "Insufficient Data"
        assert items_map["case_no_analysis"]["priority"] == "Needs Analysis"
        assert items_map["case_unverified"]["priority"] == "Needs Verification"
        assert items_map["case_ready"]["priority"] == "Ready"


def test_cases_priority_database_failure_handling():
    """Verify database errors in /api/cases/priority return 500 safely."""
    with patch("app.api.cases.get_db") as mock_get_db:
        mock_db = MagicMock()
        mock_db.documents.aggregate.side_effect = RuntimeError("DB error")
        mock_get_db.return_value = mock_db

        resp = client.get("/api/cases/priority")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Unable to load case priority data."
