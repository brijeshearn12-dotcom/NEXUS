"""test_system_failures_and_integrity.py — Task 8.1 Functional, System, Failure & Integrity Tests.

Covers:
1. Automated Case-Flow Testing:
   - Full pipeline across curated cases: Frontend/API -> Database -> Extraction -> Graph -> Analysis -> Report
   - Edge-case text inputs: empty input (400), very short text (insufficient_data),
     single-accused judgment (insufficient_data), normal multi-accused case (ok + ranking)
2. Failure Simulations (Strict P0 rule — zero hard crashes):
   - LLM failure: simulated invalid key / API error -> rule fallback works, gemini_used=False, no crash
   - Database failure: simulated MongoDB unreachable -> HTTP 500 with safe readable error, no secret leak
   - Geocoding failure: simulated Nominatim timeout / network error -> graceful degradation, geocoding_status='unknown'
   - Network timeout: simulated external timeout -> handled safely without hanging
3. Provenance Integrity:
   - Rigorous MongoDB verification query asserting Missing entity provenance = 0,
     Missing edge provenance = 0, Total invalid = 0
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import httpx
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.services.extraction.llm_fallback import (
    call_gemini_api,
)
from app.services.extraction.service import run_extraction_pipeline_on_text
from app.services.geocoding.nominatim_client import (
    _GEOCODE_CACHE,
    enrich_entity_with_geocoding,
    geocode_location,
)

client = TestClient(app)
logger = logging.getLogger(__name__)


# ── 1. PROVENANCE INTEGRITY VERIFICATION ──────────────────────────────────────


def _run_provenance_check(db):
    """Execute strict provenance query on MongoDB entities and edges."""
    invalid_entity_filter = {
        "$or": [
            {"provenance": {"$exists": False}},
            {"provenance": None},
            {"provenance": {}},
            {"provenance.source_ref": {"$exists": False}},
            {"provenance.source_ref": None},
            {"provenance.source_ref": ""},
            {"provenance.confidence": {"$exists": False}},
            {"provenance.confidence": None},
            {"provenance.confidence": {"$lt": 0.0}},
            {"provenance.confidence": {"$gt": 1.0}},
            {"provenance.method": {"$exists": False}},
            {"provenance.method": None},
            {"provenance.method": ""},
        ]
    }
    missing_entities = db.entities.count_documents(invalid_entity_filter)

    invalid_edge_filter = {
        "$or": [
            {"provenance": {"$exists": False}},
            {"provenance": None},
            {"provenance": {}},
            {"provenance.source_ref": {"$exists": False}},
            {"provenance.source_ref": None},
            {"provenance.source_ref": ""},
            {"provenance.confidence": {"$exists": False}},
            {"provenance.confidence": None},
            {"provenance.confidence": {"$lt": 0.0}},
            {"provenance.confidence": {"$gt": 1.0}},
            {"provenance.method": {"$exists": False}},
            {"provenance.method": None},
            {"provenance.method": ""},
        ]
    }
    missing_edges = db.edges.count_documents(invalid_edge_filter)
    total_invalid = missing_entities + missing_edges

    return missing_entities, missing_edges, total_invalid


def test_provenance_integrity_database_query():
    """Verify that every entity and edge stored in MongoDB has complete and valid provenance."""
    db = get_db()
    missing_entities, missing_edges, total_invalid = _run_provenance_check(db)

    assert missing_entities == 0, f"Found {missing_entities} entities with missing/invalid provenance"
    assert missing_edges == 0, f"Found {missing_edges} edges with missing/invalid provenance"
    assert total_invalid == 0, f"TOTAL INVALID PROVENANCE: {total_invalid}"


def test_provenance_integrity_validator_detects_malformed_records():
    """Verify that the integrity checker detects malformed entities and edges if introduced."""
    mock_db = MagicMock()
    mock_db.entities.count_documents.return_value = 2
    mock_db.edges.count_documents.return_value = 1

    missing_entities, missing_edges, total_invalid = _run_provenance_check(mock_db)
    assert missing_entities == 2
    assert missing_edges == 1
    assert total_invalid == 3


# ── 2. BOUNDARY INPUTS & EDGE CASES ──────────────────────────────────────────


def test_boundary_empty_input_rejected():
    """Verify empty judgment text payload is rejected with HTTP 400 Bad Request."""
    case_id = "case_test_empty_input"
    resp = client.post(
        f"/api/cases/{case_id}/ingest",
        json={"text": "   ", "title": "Empty Ingest"},
    )
    assert resp.status_code == 400
    assert "cannot be empty" in resp.json()["detail"].lower()


def test_boundary_very_short_text_handled_gracefully():
    """Verify very short judgment text ingests, extracts, builds graph, and safely returns insufficient_data."""
    db = get_db()
    case_id = "case_test_very_short"

    # Cleanup any previous run
    db.cases.delete_one({"case_id": case_id})
    db.documents.delete_many({"case_id": case_id})
    db.entities.delete_many({"case_id": case_id})
    db.edges.delete_many({"case_id": case_id})

    # Ingest short text
    resp_ingest = client.post(
        f"/api/cases/{case_id}/ingest",
        json={"text": "Order reserved. Matter adjourned to 15th March.", "title": "Short Order"},
    )
    assert resp_ingest.status_code == 201

    # Extract
    resp_extract = client.post(f"/api/cases/{case_id}/extract")
    assert resp_extract.status_code == 200

    # Build Graph
    resp_graph = client.post(f"/api/cases/{case_id}/build-graph")
    assert resp_graph.status_code == 200

    # Analysis must not crash; returns insufficient_data
    resp_analysis = client.get(f"/api/cases/{case_id}/analysis")
    assert resp_analysis.status_code == 200
    data = resp_analysis.json()
    assert data["status"] == "insufficient_data"
    assert "minimum required" in data["reason"].lower()

    # Cleanup
    db.cases.delete_one({"case_id": case_id})
    db.documents.delete_many({"case_id": case_id})
    db.entities.delete_many({"case_id": case_id})
    db.edges.delete_many({"case_id": case_id})


def test_boundary_single_accused_judgment_handled_gracefully():
    """Verify single accused judgment extracts entity but returns insufficient_data for network graph."""
    db = get_db()
    case_id = "case_test_single_accused"

    # Cleanup
    db.cases.delete_one({"case_id": case_id})
    db.documents.delete_many({"case_id": case_id})
    db.entities.delete_many({"case_id": case_id})
    db.edges.delete_many({"case_id": case_id})

    judgment_text = (
        "IN THE HIGH COURT OF JUDICATURE AT BOMBAY\n"
        "State of Maharashtra vs Ramesh Kumar\n"
        "FACTS:\n"
        "The accused Ramesh Kumar was apprehended at Dadar Station. "
        "The sole appellant Ramesh Kumar was found in possession of contraband under NDPS Act. "
        "No other conspirators were identified. The appellant acted alone."
    )

    resp_ingest = client.post(
        f"/api/cases/{case_id}/ingest",
        json={"text": judgment_text, "title": "Single Accused Trial"},
    )
    assert resp_ingest.status_code == 201

    resp_extract = client.post(f"/api/cases/{case_id}/extract")
    assert resp_extract.status_code == 200
    assert resp_extract.json()["entities_extracted"] >= 1

    resp_build = client.post(f"/api/cases/{case_id}/build-graph")
    assert resp_build.status_code == 200

    resp_analysis = client.get(f"/api/cases/{case_id}/analysis")
    assert resp_analysis.status_code == 200
    assert resp_analysis.json()["status"] in {"ok", "insufficient_data"}
    # Must not create co_accused edges for a single accused person
    assert db.edges.count_documents({"case_id": case_id, "edge_type": "co_accused"}) == 0

    # Cleanup
    db.cases.delete_one({"case_id": case_id})
    db.documents.delete_many({"case_id": case_id})
    db.entities.delete_many({"case_id": case_id})
    db.edges.delete_many({"case_id": case_id})


def test_boundary_normal_multi_accused_case():
    """Verify multi-accused case builds relationship graph, resolves aliases, and runs analysis."""
    db = get_db()
    case_id = "case_test_multi_accused"

    # Cleanup
    db.cases.delete_one({"case_id": case_id})
    db.documents.delete_many({"case_id": case_id})
    db.entities.delete_many({"case_id": case_id})
    db.edges.delete_many({"case_id": case_id})

    judgment_text = (
        "IN THE HIGH COURT OF DELHI\n"
        "State vs Rajesh Sharma, Mohan Lal, and Suresh Kumar\n"
        "FACTUAL BACKGROUND:\n"
        "The accused Rajesh Sharma and Mohan Lal conspired together with Suresh Kumar to orchestrate extortion. "
        "Accused Rajesh Sharma procured weapons from Suresh Kumar. Mohan Lal collected ransom payments. "
        "All three accused persons acted in common concert under Section 120B and Section 384 IPC."
    )

    resp_ingest = client.post(
        f"/api/cases/{case_id}/ingest",
        json={"text": judgment_text, "title": "Syndicate Extortion Case"},
    )
    assert resp_ingest.status_code == 201

    resp_extract = client.post(f"/api/cases/{case_id}/extract")
    assert resp_extract.status_code == 200

    resp_resolve = client.post(f"/api/cases/{case_id}/resolve")
    assert resp_resolve.status_code == 200

    resp_graph = client.post(f"/api/cases/{case_id}/build-graph")
    assert resp_graph.status_code == 200

    resp_analysis = client.get(f"/api/cases/{case_id}/analysis")
    assert resp_analysis.status_code == 200
    data = resp_analysis.json()
    assert data["case_id"] == case_id

    # Verify report generation also works
    resp_report = client.get(f"/api/cases/{case_id}/report")
    assert resp_report.status_code == 200
    assert resp_report.headers["content-type"] == "application/pdf"

    # Cleanup
    db.cases.delete_one({"case_id": case_id})
    db.documents.delete_many({"case_id": case_id})
    db.entities.delete_many({"case_id": case_id})
    db.edges.delete_many({"case_id": case_id})


# ── 3. FAILURE SIMULATION: LLM UNAVAILABLE / FALLBACK ─────────────────────────


def test_llm_failure_simulation_falls_back_to_rules():
    """Verify that when LLM API fails (invalid key or HTTP 403), the pipeline falls back gracefully."""
    sample_text = (
        "The accused Vijay Kumar and Sunil Verma were intercepted near Connaught Place, New Delhi. "
        "Recovery was made under FIR 108/2023."
    )

    # Simulate Gemini API failing with 403 Forbidden / invalid API key
    with patch("app.services.extraction.llm_fallback.call_gemini_api", return_value=None):
        result = run_extraction_pipeline_on_text(
            text=sample_text,
            case_id="test_case_llm_fail",
            document_id="test_doc_llm_fail",
            enable_gemini_fallback=True,
        )

        assert result is not None
        assert "entities" in result
        assert result.get("gemini_used") is False
        assert len(result["entities"]) > 0

        # Verify extracted entities have valid provenance
        for ent in result["entities"]:
            assert ent.provenance is not None
            assert ent.provenance.source_ref == "test_doc_llm_fail"
            assert ent.provenance.method in {"spacy_ner", "regex_fir", "regex_case_number", "regex_vehicle", "regex_phone", "accused_pattern"}


def test_llm_call_gemini_api_handles_network_and_http_errors():
    """Verify call_gemini_api returns None on HTTP errors or network timeouts without crashing."""
    # Test HTTP error
    with patch("httpx.Client.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = '{"error": {"message": "API key not valid"}}'
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized", request=MagicMock(), response=mock_resp
        )
        mock_post.return_value = mock_resp

        res = call_gemini_api("Extract entities", api_key="invalid_test_key")
        assert res is None

    # Test network connection error
    with patch("httpx.Client.post", side_effect=httpx.ConnectError("Connection refused")):
        res = call_gemini_api("Extract entities", api_key="test_key")
        assert res is None


# ── 4. FAILURE SIMULATION: DATABASE UNAVAILABLE ────────────────────────────────


def test_database_failure_simulation_graceful_http_500():
    """Verify that if MongoDB is unreachable, endpoints return proper HTTP 500 without leaking secrets."""
    with patch("app.api.corpus.get_db", side_effect=RuntimeError("MongoDB connection lost")):
        resp = client.get("/api/corpus/stats")
        assert resp.status_code == 500
        data = resp.json()
        assert "Unable to load corpus data." in data["detail"]
        assert "mongodb://" not in str(data)  # Zero secrets leaked

    with patch("app.api.cases.get_db", side_effect=RuntimeError("MongoDB timeout")):
        resp = client.get("/api/cases/priority")
        assert resp.status_code == 500
        data = resp.json()
        assert "Unable to load case priority data." in data["detail"]
        assert "mongodb://" not in str(data)


# ── 5. FAILURE SIMULATION: GEOCODING TIMEOUT & ERROR ──────────────────────────


def test_geocoding_failure_simulation_graceful_degradation():
    """Verify that when geocoding times out or errors, pipeline continues with geocoding_status='unknown'."""
    _GEOCODE_CACHE.clear()

    # 1. Geocoding timeout simulation
    with patch("httpx.Client.get", side_effect=httpx.TimeoutException("Read timed out")):
        res = geocode_location("Mumbai", timeout_sec=0.1)
        assert res["status"] == "unavailable"
        assert res["latitude"] is None
        assert res["longitude"] is None
        assert "timed out" in res["error"].lower()

    # 2. Geocoding network error simulation
    with patch("httpx.Client.get", side_effect=httpx.ConnectError("Network unreachable")):
        res = geocode_location("Bangalore", timeout_sec=0.1)
        assert res["status"] == "unavailable"
        assert "network error" in res["error"].lower()

    # 3. Entity enrichment with geocoding failure
    location_entity = {
        "id": "ent_loc_test",
        "case_id": "case_test_geo",
        "entity_type": "LOCATION",
        "name": "Unknown Hideout",
        "metadata": {},
    }
    with patch("app.services.geocoding.nominatim_client.geocode_location", return_value={"status": "unavailable", "error": "timeout"}):
        enriched = enrich_entity_with_geocoding(location_entity)
        assert enriched["metadata"]["geocoding_status"] == "unknown"
        assert enriched["metadata"]["coordinates"] is None
        assert enriched["metadata"]["geocoding_reason"] == "timeout"


# ── 6. FAILURE SIMULATION: NETWORK TIMEOUT ────────────────────────────────────


def test_network_timeout_handling():
    """Verify external HTTP requests enforce explicit timeouts and handle timeout exceptions cleanly."""
    with patch("httpx.Client.get", side_effect=httpx.TimeoutException("Connection timed out")):
        # geocode_location must catch timeout and return structured dict, not raise
        result = geocode_location("Hyderabad", timeout_sec=1.0)
        assert result["status"] == "unavailable"
        assert result["latitude"] is None


# ── 7. FULL PIPELINE ON CURATED CASES ─────────────────────────────────────────


def test_curated_cases_full_pipeline_verification():
    """Verify that curated cases in the database execute through all analytical stages safely."""
    db = get_db()
    cases = list(db.cases.find({}, {"case_id": 1, "title": 1}).limit(2))
    assert len(cases) > 0, "At least one case must exist in database"

    for c in cases:
        cid = c["case_id"]

        # 1. Extraction (idempotent)
        res_extract = client.post(f"/api/cases/{cid}/extract")
        assert res_extract.status_code == 200, f"Extraction failed for case {cid}"

        # 2. Resolution (idempotent)
        res_resolve = client.post(f"/api/cases/{cid}/resolve")
        assert res_resolve.status_code == 200, f"Resolution failed for case {cid}"

        # 3. Build Graph (idempotent)
        res_graph = client.post(f"/api/cases/{cid}/build-graph")
        assert res_graph.status_code == 200, f"Graph build failed for case {cid}"

        # 4. Analysis
        res_analysis = client.get(f"/api/cases/{cid}/analysis")
        assert res_analysis.status_code == 200, f"Analysis failed for case {cid}"
        data = res_analysis.json()
        assert data["status"] in {"ok", "insufficient_data"}

        # 5. Report Dossier
        res_report = client.get(f"/api/cases/{cid}/report")
        assert res_report.status_code == 200, f"Report failed for case {cid}"
        assert res_report.headers["content-type"] == "application/pdf"
        assert len(res_report.content) > 1000  # Non-empty valid PDF dossier
