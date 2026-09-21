"""Automated tests for Task 3.1 — Rule-Based + spaCy + Gemini Fallback Entity Extraction."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.models.enums import VerificationStatus
from app.services.extraction.accused_extractor import extract_accused_entities
from app.services.extraction.deduplication import (
    deduplicate_entities,
    generate_stable_entity_id,
    normalize_name,
)
from app.services.extraction.legal_role_filter import (
    filter_legal_roles,
    is_legal_role,
)
from app.services.extraction.llm_fallback import (
    check_devanagari_presence,
    extract_with_gemini_fallback,
    parse_and_validate_gemini_json,
    should_trigger_fallback,
)
from app.services.extraction.regex_extractors import (
    extract_all_regex,
    extract_case_numbers,
    extract_fir_numbers,
    extract_phone_numbers,
    extract_vehicles,
)
from app.services.extraction.service import run_extraction_pipeline_on_text
from app.services.extraction.spacy_extractor import extract_spacy_entities, get_spacy_nlp

client = TestClient(app)


# ── 1. REGEX TESTS ────────────────────────────────────────────────────────────


def test_regex_phone_valid():
    text = (
        "The accused used mobile numbers 9876543210 and +91 9811223344 during the offense. "
        "Also contacted +91-8765432109 from tower location."
    )
    phones = extract_phone_numbers(text)
    phone_names = [p["name"] for p in phones]
    assert "+919876543210" in phone_names
    assert "+919811223344" in phone_names
    assert "+918765432109" in phone_names
    for p in phones:
        assert p["method"] == "regex_phone"
        assert p["entity_type"] == "PHONE"
        assert p["evidence_snippet"] != ""
        assert p["confidence"] >= 0.85


def test_regex_phone_invalid_and_exclusions():
    # Pincodes, IPC sections, monetary amounts, or short numbers should not match
    text = (
        "Convicted u/s 302/34 IPC with fine of Rs. 50000/-. Pin code 110001 was noted. "
        "Year 1998 in section 138. Serial 12345."
    )
    phones = extract_phone_numbers(text)
    assert len(phones) == 0


def test_regex_vehicle_valid():
    text = (
        "The getaway car was a white sedan bearing registration MH12AB1234. "
        "Another truck DL-01-CA-1234 and bike KA 02 XY 5678 were seized at the checkpoint."
    )
    vehicles = extract_vehicles(text)
    vehicle_names = [v["name"] for v in vehicles]
    assert "MH12AB1234" in vehicle_names
    assert "DL01CA1234" in vehicle_names
    assert "KA02XY5678" in vehicle_names
    for v in vehicles:
        assert v["method"] == "regex_vehicle"
        assert v["entity_type"] == "VEHICLE"
        assert v["evidence_snippet"] != ""


def test_regex_vehicle_invalid_state_codes():
    # ZZ and XX are not valid Indian state codes
    text = "False registrations ZZ12AB1234 and XX-99-ZZ-0000 were mentioned in argument."
    vehicles = extract_vehicles(text)
    assert len(vehicles) == 0


def test_regex_fir_numbers():
    text = (
        "Registered under FIR No. 123/2022 at Crime Branch. "
        "Also connected with F.I.R. No. 456 of 2021 and Crime No. 78/2020."
    )
    firs = extract_fir_numbers(text)
    assert len(firs) >= 3
    names = [f["name"] for f in firs]
    assert any("123/2022" in n for n in names)
    assert any("456/2021" in n for n in names)
    assert any("78/2020" in n for n in names)
    for f in firs:
        assert f["method"] == "regex_fir"
        assert f["entity_type"] == "FIR"


def test_regex_case_numbers():
    text = (
        "Heard in Criminal Appeal No. 123 of 2022 arising out of Sessions Case No. 45 of 2021. "
        "Special Leave Petition (Criminal) No. 789 of 2020 was dismissed."
    )
    cases = extract_case_numbers(text)
    assert len(cases) >= 3
    case_types = [c["entity_type"] for c in cases]
    assert all(t == "CASE_NUMBER" for t in case_types)
    names = [c["name"] for c in cases]
    assert any("Criminal Appeal No. 123 of 2022" in n for n in names)
    assert any("Sessions Case No. 45 of 2021" in n for n in names)
    assert any("Special Leave Petition (Criminal) No. 789 of 2020" in n for n in names)


# ── 2. SPACY NER TESTS ────────────────────────────────────────────────────────


def test_spacy_model_loads_reliably():
    nlp = get_spacy_nlp()
    assert nlp is not None
    assert nlp.meta["name"] == "core_web_sm"


def test_spacy_extracts_person_org_location():
    text = (
        "Rajesh Kumar and Vikram Malhotra held a secret meeting in Mumbai "
        "near the headquarters of Reserve Bank of India."
    )
    entities = extract_spacy_entities(text)
    types = {e["entity_type"] for e in entities}
    assert "PERSON" in types
    assert "LOCATION" in types
    assert "ORGANIZATION" in types

    names = [e["name"] for e in entities]
    assert any("Rajesh Kumar" in n for n in names)
    assert any("Mumbai" in n for n in names)
    assert any("Reserve Bank of India" in n for n in names)
    for e in entities:
        assert e["method"] == "spacy_ner"
        assert e["evidence_snippet"] != ""
        assert 0.0 <= e["confidence"] <= 1.0


# ── 3. LEGAL-ROLE FILTER TESTS ────────────────────────────────────────────────


def test_legal_role_filter_counsel_and_judges():
    # Obvious judges and counsels should be filtered
    text = (
        "Hon'ble Mr. Justice R.F. Nariman presided over the bench. "
        "Advocate Rajesh Sharma appeared for the accused. "
        "Learned Public Prosecutor Shri Anand Verma argued the case."
    )
    candidates = [
        {"name": "R.F. Nariman", "entity_type": "PERSON", "start_char": text.index("R.F. Nariman"), "end_char": text.index("R.F. Nariman") + 12},
        {"name": "Rajesh Sharma", "entity_type": "PERSON", "start_char": text.index("Rajesh Sharma"), "end_char": text.index("Rajesh Sharma") + 13},
        {"name": "Anand Verma", "entity_type": "PERSON", "start_char": text.index("Anand Verma"), "end_char": text.index("Anand Verma") + 11},
    ]
    accepted, filtered = filter_legal_roles(candidates, text)
    assert len(accepted) == 0
    assert len(filtered) == 3
    reasons = [f["filter_reason"] for f in filtered]
    assert any("judicial" in r for r in reasons)
    assert any("counsel" in r for r in reasons)


def test_legal_role_filter_retains_ordinary_persons():
    # Ordinary persons mentioned without legal titles should be retained
    text = "Rajesh Sharma met A-1 near the railway station and handed over the package."
    candidates = [
        {
            "name": "Rajesh Sharma",
            "entity_type": "PERSON",
            "start_char": text.index("Rajesh Sharma"),
            "end_char": text.index("Rajesh Sharma") + 13,
            "evidence_snippet": text,
        }
    ]
    accepted, filtered = filter_legal_roles(candidates, text)
    assert len(accepted) == 1
    assert len(filtered) == 0
    assert accepted[0]["name"] == "Rajesh Sharma"


# ── 4. ACCUSED EXTRACTION TESTS ───────────────────────────────────────────────


def test_accused_extraction_identifiers():
    text = "A-1 was present with A-2 and A-3. Later accused No. 4 arrived while Accused 5 fled."
    entities = extract_accused_entities(text)
    accused_ids = [e.get("accused_id") for e in entities]
    assert "A-1" in accused_ids
    assert "A-2" in accused_ids
    assert "A-3" in accused_ids
    assert "A-4" in accused_ids
    assert "A-5" in accused_ids
    for e in entities:
        assert e["method"] == "accused_pattern"


def test_accused_multi_range_expansion():
    text = "Charges were framed against Accused Nos. 2 to 4 and Accused Nos. 6 and 7."
    entities = extract_accused_entities(text)
    ids = {e.get("accused_id") for e in entities}
    assert {"A-2", "A-3", "A-4"}.issubset(ids)
    assert {"A-6", "A-7"}.issubset(ids)


def test_accused_explicit_name_mapping():
    text = "A-1 Rajesh Kumar and A-2 Suresh Kumar hatched the conspiracy with co-accused Mahesh Patel."
    entities = extract_accused_entities(text)
    names = {e["name"] for e in entities}
    assert "Rajesh Kumar" in names
    assert "Suresh Kumar" in names
    assert "Mahesh Patel" in names

    rajesh = next(e for e in entities if e["name"] == "Rajesh Kumar")
    assert rajesh["accused_id"] == "A-1"
    assert rajesh["entity_type"] == "PERSON"
    assert rajesh["metadata"]["is_accused"] is True


# ── 5. NORMALIZATION, DEDUPLICATION & PROVENANCE TESTS ────────────────────────


def test_normalization_and_deduplication():
    cands = [
        {"name": "Mr. Rajesh Kumar", "entity_type": "PERSON", "method": "spacy_ner", "confidence": 0.85, "evidence_snippet": "...Mr. Rajesh Kumar was present..."},
        {"name": "Rajesh Kumar", "entity_type": "PERSON", "method": "accused_pattern", "accused_id": "A-1", "confidence": 0.95, "evidence_snippet": "...A-1 Rajesh Kumar met near Mumbai..."},
        {"name": "MH-12-AB-1234", "entity_type": "VEHICLE", "method": "regex_vehicle", "confidence": 0.92, "evidence_snippet": "...MH-12-AB-1234 was driven..."},
        {"name": "MH12AB1234", "entity_type": "VEHICLE", "method": "regex_vehicle", "confidence": 0.92, "evidence_snippet": "...MH12AB1234 spotted..."},
    ]
    deduped = deduplicate_entities(cands, "case_001", "doc_001")
    assert len(deduped) == 2  # 1 PERSON + 1 VEHICLE

    person = next(e for e in deduped if e["entity_type"] == "PERSON")
    assert person["name"] == "Rajesh Kumar"
    assert "A-1" in person["aliases"]
    assert "spacy_ner" in person["metadata"]["extraction_methods"]
    assert "accused_pattern" in person["metadata"]["extraction_methods"]

    vehicle = next(e for e in deduped if e["entity_type"] == "VEHICLE")
    assert vehicle["name"] == "MH12AB1234"


def test_provenance_and_verification_status_on_extracted_entities():
    text = "A-1 Rajesh Kumar drove vehicle MH12AB1234 and called +91 9876543210 in Crime No. 12/2021."
    res = run_extraction_pipeline_on_text(text, "case_101", "doc_101", enable_gemini_fallback=False)
    entities = res["entities"]
    assert len(entities) >= 4

    for ent in entities:
        # Check Entity model fields
        assert ent.id.startswith("ent_case_101_")
        assert ent.case_id == "case_101"
        assert ent.document_id == "doc_101"
        assert ent.verification_status == VerificationStatus.UNVERIFIED
        assert ent.evidence_snippet is not None
        assert ent.evidence_snippet != ""

        # Check Provenance model
        prov = ent.provenance
        assert prov.tier == "primary"
        assert prov.source_ref == "doc_101"
        assert prov.method in {"regex_phone", "regex_vehicle", "regex_fir", "accused_pattern", "spacy_ner"}
        assert 0.0 <= prov.confidence <= 1.0


# ── 6. GEMINI FALLBACK & RESILIENCE TESTS ──────────────────────────────────────


def test_gemini_fallback_trigger_conditions():
    # Long text with zero entities triggers Condition A (low yield)
    long_blank = "The court considered several procedural questions regarding the hearing schedule and administrative dates. " * 10
    trigger, reason = should_trigger_fallback(long_blank, [])
    assert trigger is True
    assert "condition_a_low_yield" in reason

    # Hindi Devanagari text triggers Condition B
    hindi_text = "आरोपी राजेश कुमार ने घटना स्थल पर उपस्थित होकर अपराध स्वीकार किया।"
    trigger_hindi, reason_hindi = should_trigger_fallback(hindi_text, [])
    assert trigger_hindi is True
    assert reason_hindi == "condition_b_devanagari_text"


def test_gemini_parse_valid_json():
    source_text = "Sunil Sharma visited the bank branch in Kanpur on Monday."
    gemini_output = json.dumps([
        {"name": "Sunil Sharma", "entity_type": "PERSON", "evidence": "Sunil Sharma visited the bank"},
        {"name": "Kanpur", "entity_type": "LOCATION", "evidence": "branch in Kanpur"},
    ])
    validated = parse_and_validate_gemini_json(gemini_output, source_text)
    assert len(validated) == 2
    assert validated[0]["name"] == "Sunil Sharma"
    assert validated[0]["entity_type"] == "PERSON"
    assert validated[1]["name"] == "Kanpur"
    assert validated[1]["entity_type"] == "LOCATION"
    assert validated[0]["method"] == "gemini_fallback"


def test_gemini_parse_rejects_hallucinations_not_in_source():
    source_text = "Only John Doe was present at the scene."
    gemini_output = json.dumps([
        {"name": "John Doe", "entity_type": "PERSON", "evidence": "John Doe was present"},
        {"name": "Ghost Actor", "entity_type": "PERSON", "evidence": "Ghost Actor fled to Paris"},
    ])
    validated = parse_and_validate_gemini_json(gemini_output, source_text)
    assert len(validated) == 1
    assert validated[0]["name"] == "John Doe"


def test_gemini_invalid_json_handling():
    source_text = "Some text here."
    invalid_json = "This is not JSON at all {broken"
    validated = parse_and_validate_gemini_json(invalid_json, source_text)
    assert validated == []


def test_gemini_api_failure_and_missing_key_resilience():
    # Missing API key safely disables fallback and returns []
    res = extract_with_gemini_fallback("Sample text", api_key="")
    assert res == []

    # Mock HTTP 500 error from Gemini API
    mock_client = MagicMock(spec=httpx.Client)
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError("500 Server Error", request=MagicMock(), response=mock_resp)
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"
    mock_client.post.return_value = mock_resp

    res_mock = extract_with_gemini_fallback("Sample text", api_key="dummy_key", client=mock_client)
    assert res_mock == []


def test_deterministic_pipeline_unaffected_when_gemini_disabled():
    text = "A-1 Rajesh Kumar drove vehicle MH12AB1234 in Crime No. 99/2021."
    res = run_extraction_pipeline_on_text(
        text,
        "case_no_gemini",
        "doc_no_gemini",
        enable_gemini_fallback=False,
    )
    assert res["gemini_used"] is False
    assert res["entities_extracted"] >= 3
    assert any(e.name == "Rajesh Kumar" for e in res["entities"])
    assert any(e.name == "MH12AB1234" for e in res["entities"])


# ── 7. EXTRACTION API TESTS ───────────────────────────────────────────────────


def test_api_extraction_run_validation():
    # Missing document_id
    response = client.post("/api/extraction/run", json={})
    assert response.status_code == 422

    # Nonexistent document ID
    response = client.post("/api/extraction/run", json={"document_id": "doc_nonexistent_xyz_123"})
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_api_extraction_run_idempotency_and_success():
    # Run on one of the real curated documents in MongoDB (e.g. doc_100478559)
    resp1 = client.post("/api/extraction/run", json={"document_id": "doc_100478559", "enable_gemini_fallback": False})
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["document_id"] == "doc_100478559"
    assert data1["entities_extracted"] > 0
    assert "by_method" in data1
    assert data1["gemini_used"] is False

    # Second run should produce the exact same entity count and same entity IDs
    resp2 = client.post("/api/extraction/run", json={"document_id": "doc_100478559", "enable_gemini_fallback": False})
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["entities_extracted"] == data1["entities_extracted"]
    ids1 = {e["id"] for e in data1["entities"]}
    ids2 = {e["id"] for e in data2["entities"]}
    assert ids1 == ids2


def test_api_entities_query_endpoints():
    # Test listing entities with filters
    resp = client.get("/api/entities/?document_id=doc_100478559")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    first_id = data["items"][0]["id"]

    # Test single entity retrieval
    resp_single = client.get(f"/api/entities/{first_id}")
    assert resp_single.status_code == 200
    assert resp_single.json()["id"] == first_id


def test_accused_single_name_and_variations():
    text = "A-1 Balakarupasamy and Accused A-2 Rajesh were spotted by co-accused Selvam."
    entities = extract_accused_entities(text)
    names = {e["name"] for e in entities}
    assert "Balakarupasamy" in names
    assert "Rajesh" in names
    assert "Selvam" in names


def test_extract_all_regex_combined():
    text = "Crime No. 45/2021 registered against driver of MH12AB1234 who called 9876543210 in Crl.A. No. 12/2022."
    results = extract_all_regex(text)
    types = {r["entity_type"] for r in results}
    assert "FIR" in types
    assert "VEHICLE" in types
    assert "PHONE" in types
    assert "CASE_NUMBER" in types


def test_normalize_name_and_stable_id():
    norm, acc = normalize_name("Mr. Rajesh Kumar", "PERSON")
    assert norm == "Rajesh Kumar"
    assert acc is None

    norm_veh, _ = normalize_name("mh-12-ab-1234", "VEHICLE")
    assert norm_veh == "MH12AB1234"

    id1 = generate_stable_entity_id("case_1", "PERSON", "Rajesh Kumar")
    id2 = generate_stable_entity_id("case_1", "PERSON", "Rajesh Kumar")
    assert id1 == id2
    assert id1.startswith("ent_case_1_")


def test_is_legal_role_direct():
    text = "Hon'ble Mr. Justice R.F. Nariman and learned counsel Shri Verma appeared."
    is_judge, reason = is_legal_role("R.F. Nariman", text, text.index("R.F. Nariman"), text.index("R.F. Nariman") + 12)
    assert is_judge is True
    assert "judicial" in reason

    is_adv, reason_adv = is_legal_role("Shri Verma", text, text.index("Shri Verma"), text.index("Shri Verma") + 10)
    assert is_adv is True


def test_check_devanagari_presence_direct():
    english_text = "This is purely English text."
    assert check_devanagari_presence(english_text) is False

    hindi_text = "यह भारतीय कानूनी दस्तावेज का अंश है।"
    assert check_devanagari_presence(hindi_text, min_chars=5) is True


# ── 8. TASK 3.2 EXTRACTION ENDPOINTS & PERSISTENCE TESTS ──────────────────────


def test_api_document_extract_endpoint_success():
    # Individual extraction endpoint POST /api/documents/{id}/extract
    resp = client.post("/api/documents/doc_100478559/extract?enable_gemini_fallback=false")
    assert resp.status_code == 200
    data = resp.json()
    assert data["document_id"] == "doc_100478559"
    assert data["status"] == "success"
    assert data["entities_extracted"] > 0
    assert "by_method" in data
    assert "by_type" in data
    assert len(data["entities"]) == data["entities_extracted"]

    # Verify entities are persisted in MongoDB
    resp_ents = client.get("/api/entities/?document_id=doc_100478559")
    assert resp_ents.status_code == 200
    assert resp_ents.json()["total"] == data["entities_extracted"]


def test_api_document_extract_endpoint_missing_doc():
    resp = client.post("/api/documents/doc_missing_nonexistent_999/extract")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_api_document_extract_endpoint_empty_text():
    from app.core.db import get_collection
    db_docs = get_collection("documents")

    # Insert temporary empty document
    temp_id = "doc_test_empty_temporary"
    db_docs.insert_one({"id": temp_id, "case_id": "case_empty", "title": "Empty Doc", "text": "   ", "raw_text": ""})

    try:
        resp = client.post(f"/api/documents/{temp_id}/extract")
        assert resp.status_code == 400
        assert "empty text" in resp.json()["detail"].lower()
    finally:
        db_docs.delete_one({"id": temp_id})


def test_api_document_extract_failure_handling():
    with patch("app.api.documents.extract_and_store_document") as mock_extract:
        mock_extract.side_effect = RuntimeError("Database connection timed out")
        resp = client.post("/api/documents/doc_100478559/extract")
        assert resp.status_code == 500
        assert "Database connection timed out" in resp.json()["detail"]


def test_api_corpus_extract_all_endpoint():
    # Batch corpus extraction POST /api/corpus/extract-all
    resp = client.post("/api/corpus/extract-all?enable_gemini_fallback=false")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_documents"] >= 20
    assert data["successful_documents"] >= 20
    assert data["failed_documents"] == 0
    assert data["total_entities_extracted"] > 0
    assert "entity_counts_by_type" in data
    assert "entity_counts_by_method" in data
    assert "processing_duration_sec" in data
    assert isinstance(data["error_details"], list)


def test_api_documents_list_and_get():
    # List documents
    resp_list = client.get("/api/documents/")
    assert resp_list.status_code == 200
    data = resp_list.json()
    assert data["total"] >= 20
    assert len(data["items"]) >= 1

    first = data["items"][0]
    assert "id" in first
    assert "title" in first
    assert "entities_count" in first
    assert "extraction_status" in first

    # Get single document
    doc_id = first["id"]
    resp_get = client.get(f"/api/documents/{doc_id}")
    assert resp_get.status_code == 200
    doc_data = resp_get.json()
    assert doc_data["id"] == doc_id
    assert "text" in doc_data
    assert "entities_count" in doc_data


def test_api_entities_search_and_filter():
    # Search by name
    resp_search = client.get("/api/entities/?q=Balakarupasamy")
    assert resp_search.status_code == 200
    data = resp_search.json()
    assert data["total"] >= 1
    assert any("Balakarupasamy" in e["name"] for e in data["items"])

    # Filter by method
    resp_method = client.get("/api/entities/?method=regex_fir")
    assert resp_method.status_code == 200
    data_method = resp_method.json()
    assert all(e["provenance"]["method"] == "regex_fir" for e in data_method["items"])
