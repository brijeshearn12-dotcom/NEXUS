"""Automated test suite for Task 2.2 — Boilerplate Stripping & Corpus Ingestion API."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import get_db
from app.main import app
from app.services.fact_segmenter import segment_facts
from app.services.text_cleaner import clean, clean_judgment_text

# ── Text Cleaner Unit Tests ───────────────────────────────────────────────────


def test_clean_boilerplate_removal_preserves_narrative():
    raw_sample = (
        "<html><body>\n"
        '<h2 class="doc_title">Balakarupasamy vs State on 13 August, 2019</h2>\n'
        '<h3 class="doc_author">Author: J.Nisha Banu</h3>\n'
        '<h3 class="doc_bench">Bench: J. Nisha Banu, N. Anand Venkatesh</h3>\n'
        '<pre id="pre_1">\n'
        "BEFORE THE MADURAI BENCH OF MADRAS HIGH COURT\n"
        "RESERVED ON : 19.09.2022\n"
        "DELIVERED ON : 23.09.2022\n"
        "CORAM :\n"
        "THE HONOURABLE MRS.JUSTICE J. NISHA BANU\n"
        "Crl.A.(MD)Nos.451 of 2019\n"
        "For Appellant : Mr. R. Anand, learned counsel\n"
        "For Respondent : Mr. A. Thiruvadikumar, Additional Public Prosecutor\n"
        "___________________________________\n"
        "https://www.mhc.tn.gov.in/judis\n"
        "Page No.1/72\n"
        "\x0c\n"
        "Balakarupasamy and Mariyappan @ Ashok (Accused No. 1 and 2) entered into a criminal conspiracy "
        "on 15.08.2011 in Tuticorin. Accused A-1 contacted P.W-2 on mobile number 9942533301 demanding "
        "a ransom of Rs. 50,00,000/- under Section 120-B read with Section 364-A of IPC.\n"
        "Sd/- Judge\n"
        "</pre></body></html>"
    )

    cleaned, meta = clean_judgment_text(raw_sample)

    # Verify boilerplate removed
    assert "BEFORE THE MADURAI BENCH" not in cleaned
    assert "RESERVED ON" not in cleaned
    assert "CORAM" not in cleaned
    assert "Page No.1/72" not in cleaned
    assert "https://www.mhc.tn.gov.in/judis" not in cleaned
    assert "For Appellant" not in cleaned
    assert "Sd/- Judge" not in cleaned
    assert "<h2" not in cleaned

    # Verify substantive narrative survived
    assert "Balakarupasamy" in cleaned
    assert "Mariyappan @ Ashok" in cleaned
    assert "Tuticorin" in cleaned
    assert "15.08.2011" in cleaned
    assert "Section 120-B" in cleaned
    assert "9942533301" in cleaned
    assert "Rs. 50,00,000/-" in cleaned

    # Verify clean helper wrapper
    assert clean(raw_sample) == cleaned
    assert meta["original_length"] > meta["cleaned_length"]
    assert 0.0 < meta["retention_ratio"] < 1.0


def test_clean_empty_or_whitespace_text():
    cleaned, meta = clean_judgment_text("   \n\n\t   ")
    assert cleaned == ""
    assert meta["cleaned_length"] == 0
    assert meta["retention_ratio"] == 0.0
    assert len(meta["warnings"]) > 0


# ── Fact Segmenter Unit Tests ─────────────────────────────────────────────────


def test_segment_facts_with_heading():
    text = (
        "Preliminary background and procedural history.\n\n"
        "CASE OF THE PROSECUTION:\n"
        "The prosecution case is that on 12.04.2018, accused A1 and A2 procured illegal arms "
        "and met at hotel Grand Residency to coordinate the attack. Call logs establish 23 contacts.\n\n"
        "SUBMISSIONS OF THE APPELLANT:\n"
        "Learned counsel for the appellant submits that no recovery was effected."
    )
    result = segment_facts(text)
    assert result["method"] == "heading_match"
    assert result["confidence"] >= 0.8
    assert "prosecution" in result["section_name"].lower()
    assert "Grand Residency" in result["text"]
    assert "SUBMISSIONS OF THE APPELLANT" not in result["text"]


def test_segment_facts_case_insensitive():
    text = (
        "General introduction.\n\n"
        "factual background:\n"
        "The deceased was last seen with the accused near the river bank on 20th January.\n\n"
        "ARGUMENTS:\n"
        "Counsel argued lack of motive."
    )
    result = segment_facts(text)
    assert result["method"] == "heading_match"
    assert "factual background" in result["section_name"].lower()
    assert "river bank" in result["text"]


def test_segment_facts_fallback():
    text = (
        "This is an order discussing bail under Section 439 CrPC. "
        "The petitioner has been in custody for 14 months. "
        "No explicit fact header exists in this short order."
    )
    result = segment_facts(text)
    assert result["method"] == "fallback"
    assert result["section_name"] == "full_text_fallback"
    assert result["confidence"] == 0.50
    assert result["text"] == text


# ── API Endpoint Integration Tests ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_api_corpus_load_and_idempotency():
    """Verify loading curated corpus and idempotency on repeated execution."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # First load
        res1 = await client.post("/api/corpus/load")
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["status"] == "ok"
        assert data1["total"] == 20
        assert data1["failed"] == 0
        assert data1["inserted"] + data1["updated"] == 20

        # Verify documents collection count
        db = get_db()
        assert db.documents.count_documents({}) == 20

        # Second load — verify idempotency
        res2 = await client.post("/api/corpus/load")
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["status"] == "ok"
        assert data2["total"] == 20
        assert data2["updated"] == 20
        assert data2["inserted"] == 0

        # Collection count must still remain exactly 20
        assert db.documents.count_documents({}) == 20


@pytest.mark.asyncio
async def test_api_get_corpus_list():
    """Verify paginated listing of lightweight corpus metadata."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/corpus?page=1&limit=5")
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert len(data["items"]) <= 5
        assert data["total"] == 20
        assert data["page"] == 1
        assert data["limit"] == 5

        first_item = data["items"][0]
        assert "id" in first_item
        assert "case_id" in first_item
        assert "title" in first_item
        assert "verification_status" in first_item
        # Verify heavy text bodies are omitted in the list view
        assert "text" not in first_item
        assert "raw_text" not in first_item


@pytest.mark.asyncio
async def test_api_get_corpus_document_by_id():
    """Verify retrieving full document with cleaned text and extraction segment."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Fetch known curated document
        res = await client.get("/api/corpus/doc_100478559")
        assert res.status_code == 200
        doc = res.json()
        assert doc["id"] == "doc_100478559"
        assert "Balakarupasamy" in doc["title"]
        assert len(doc["text"]) > 1000
        assert "provenance" in doc
        assert doc["provenance"]["tier"] == "primary"
        assert "cleaning_metadata" in doc
        assert "segmentation_metadata" in doc
        assert doc["verification_status"] == "unverified"


@pytest.mark.asyncio
async def test_api_get_corpus_document_not_found():
    """Verify HTTP 404 for nonexistent document ID."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/corpus/doc_does_not_exist_99999")
        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_api_manual_case_ingest_valid_and_errors():
    """Verify manual document ingestion under a case and error responses."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Valid manual ingest
        valid_payload = {
            "text": "The accused Vikrant along with co-conspirators operated an extortion racket in Pune during 2020.",
            "title": "State of Maharashtra vs Vikrant",
            "source_ref": "FIR-102/2020",
        }
        res_valid = await client.post("/api/cases/case_manual_test_1/ingest", json=valid_payload)
        assert res_valid.status_code == 201
        res_data = res_valid.json()
        assert res_data["status"] == "created"
        doc = res_data["document"]
        assert doc["case_id"] == "case_manual_test_1"
        assert doc["provenance"]["tier"] == "secondary"
        assert doc["provenance"]["method"] == "manual"

        # 2. Empty text validation -> 400 Bad Request
        res_empty = await client.post("/api/cases/case_manual_test_1/ingest", json={"text": "   "})
        assert res_empty.status_code == 400
        assert "required and cannot be empty" in res_empty.json()["detail"]

        # 3. Oversized input validation -> 413 Request Entity Too Large
        oversized_payload = {"text": "A" * 5_000_001}
        res_large = await client.post(
            "/api/cases/case_manual_test_1/ingest", json=oversized_payload
        )
        assert res_large.status_code == 413
        assert "Payload too large" in res_large.json()["detail"]

        # Clean up test manual document from database
        db = get_db()
        db.documents.delete_many({"case_id": "case_manual_test_1"})
        db.cases.delete_one({"case_id": "case_manual_test_1"})
        db.audit_log.delete_many({"case_id": "case_manual_test_1"})
