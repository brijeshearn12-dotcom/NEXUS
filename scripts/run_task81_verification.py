"""run_task81_verification.py — Comprehensive automated test runner for NEXUS Task 8.1.

SIH26189GREEN | AI-Powered Criminal Network Analysis System

Executes:
1. Curated cases full pipeline flow (Frontend/API -> DB -> Extraction -> Graph -> Analysis -> Report)
2. Boundary input tests (empty input, short input, single-accused, multi-accused)
3. Failure simulation tests (LLM fallback, MongoDB failure, Geocoding degradation, Network timeout)
4. Automated MongoDB Provenance Integrity verification
5. Prints real exact results in required format.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from unittest.mock import patch

# Ensure backend imports work
backend_dir = str(Path(__file__).resolve().parent.parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.db import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.extraction.llm_fallback import call_gemini_api  # noqa: E402
from app.services.extraction.service import run_extraction_pipeline_on_text  # noqa: E402
from app.services.geocoding.nominatim_client import (  # noqa: E402
    _GEOCODE_CACHE,
    enrich_entity_with_geocoding,
    geocode_location,
)
from scripts.verify_provenance_integrity import verify_provenance_integrity  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("task81_runner")

client = TestClient(app)


def test_curated_cases() -> bool:
    """Run curated cases through full pipeline: Extract -> Resolve -> Build Graph -> Analyze -> Report."""
    print("\n[1/5] Testing Curated Cases Pipeline...")
    db = get_db()
    cases = list(db.cases.find({}, {"case_id": 1, "title": 1}).limit(2))
    if not cases:
        print("  FAIL: No curated cases found in database.")
        return False

    for c in cases:
        cid = c["case_id"]
        # Extract
        r_ext = client.post(f"/api/cases/{cid}/extract")
        if r_ext.status_code != 200:
            print(f"  FAIL: Extract failed for {cid}: {r_ext.status_code}")
            return False

        # Resolve
        r_res = client.post(f"/api/cases/{cid}/resolve")
        if r_res.status_code != 200:
            print(f"  FAIL: Resolve failed for {cid}: {r_res.status_code}")
            return False

        # Build Graph (with transient reconnect retry)
        for attempt in range(2):
            r_grp = client.post(f"/api/cases/{cid}/build-graph")
            if r_grp.status_code == 200:
                break
        if r_grp.status_code != 200:
            print(f"  FAIL: Build graph failed for {cid}: {r_grp.status_code}")
            return False

        # Analysis
        r_ana = client.get(f"/api/cases/{cid}/analysis")
        if r_ana.status_code != 200:
            print(f"  FAIL: Analysis failed for {cid}: {r_ana.status_code}")
            return False

        # Report Dossier
        r_rep = client.get(f"/api/cases/{cid}/report")
        if r_rep.status_code != 200 or r_rep.headers.get("content-type") != "application/pdf":
            print(f"  FAIL: Report failed for {cid}: {r_rep.status_code}")
            return False

        print(f"  PASS: Case {cid} fully verified across 5 analytical stages.")

    return True


def test_boundary_inputs() -> tuple[bool, bool, bool, bool]:
    """Test empty, short, single-accused, and multi-accused boundary inputs."""
    print("\n[2/5] Testing Boundary Inputs...")
    db = get_db()

    # 1. Empty input
    r_empty = client.post("/api/cases/case_test_empty/ingest", json={"text": "   ", "title": "Empty"})
    empty_pass = r_empty.status_code == 400
    print(f"  Empty input rejection (HTTP 400): {'PASS' if empty_pass else 'FAIL'}")

    # 2. Short input
    cid_short = "case_test_short_auto"
    db.cases.delete_one({"case_id": cid_short})
    db.documents.delete_many({"case_id": cid_short})
    r_ing = client.post(f"/api/cases/{cid_short}/ingest", json={"text": "Order reserved.", "title": "Short"})
    client.post(f"/api/cases/{cid_short}/extract")
    client.post(f"/api/cases/{cid_short}/build-graph")
    r_ana = client.get(f"/api/cases/{cid_short}/analysis")
    short_pass = r_ing.status_code == 201 and r_ana.status_code == 200 and r_ana.json().get("status") == "insufficient_data"
    print(f"  Short input graceful handling (insufficient_data): {'PASS' if short_pass else 'FAIL'}")
    db.cases.delete_one({"case_id": cid_short})
    db.documents.delete_many({"case_id": cid_short})

    # 3. Single-accused
    cid_single = "case_test_single_auto"
    db.cases.delete_one({"case_id": cid_single})
    db.documents.delete_many({"case_id": cid_single})
    db.entities.delete_many({"case_id": cid_single})
    r_single_ing = client.post(
        f"/api/cases/{cid_single}/ingest",
        json={"text": "State vs Suresh Verma. The accused Suresh Verma acted alone and is convicted under Section 302.", "title": "Single"},
    )
    client.post(f"/api/cases/{cid_single}/extract")
    client.post(f"/api/cases/{cid_single}/build-graph")
    r_single_ana = client.get(f"/api/cases/{cid_single}/analysis")
    single_pass = (
        r_single_ing.status_code == 201
        and r_single_ana.status_code == 200
        and r_single_ana.json().get("status") in {"ok", "insufficient_data"}
        and db.edges.count_documents({"case_id": cid_single, "edge_type": "co_accused"}) == 0
    )
    print(f"  Single-accused judgment handling: {'PASS' if single_pass else 'FAIL'}")
    db.cases.delete_one({"case_id": cid_single})
    db.documents.delete_many({"case_id": cid_single})
    db.entities.delete_many({"case_id": cid_single})

    # 4. Multi-accused
    cid_multi = "case_test_multi_auto"
    db.cases.delete_one({"case_id": cid_multi})
    db.documents.delete_many({"case_id": cid_multi})
    db.entities.delete_many({"case_id": cid_multi})
    db.edges.delete_many({"case_id": cid_multi})
    r_multi_ing = client.post(
        f"/api/cases/{cid_multi}/ingest",
        json={
            "text": "State vs Amar Singh and Prem Kumar. The accused Amar Singh conspired with Prem Kumar to traffic narcotics.",
            "title": "Multi Accused",
        },
    )
    client.post(f"/api/cases/{cid_multi}/extract")
    client.post(f"/api/cases/{cid_multi}/resolve")
    client.post(f"/api/cases/{cid_multi}/build-graph")
    r_multi_ana = client.get(f"/api/cases/{cid_multi}/analysis")
    multi_pass = r_multi_ing.status_code == 201 and r_multi_ana.status_code == 200
    print(f"  Multi-accused judgment network flow: {'PASS' if multi_pass else 'FAIL'}")
    db.cases.delete_one({"case_id": cid_multi})
    db.documents.delete_many({"case_id": cid_multi})
    db.entities.delete_many({"case_id": cid_multi})
    db.edges.delete_many({"case_id": cid_multi})

    return empty_pass, short_pass, single_pass, multi_pass


def test_failure_simulations() -> tuple[bool, bool, bool, bool]:
    """Test LLM fallback, DB failure, Geocoding degradation, and Network timeout."""
    print("\n[3/5] Testing Failure Simulations (P0 Rule: Zero Crashes)...")

    # 1. LLM Failure Fallback
    with patch("app.services.extraction.llm_fallback.call_gemini_api", return_value=None):
        res = run_extraction_pipeline_on_text(
            text="The accused Anand Kumar was apprehended under FIR 45/2021 in New Delhi.",
            case_id="case_fail_llm",
            document_id="doc_fail_llm",
            enable_gemini_fallback=True,
        )
        llm_pass = (
            res is not None
            and res.get("gemini_used") is False
            and len(res.get("entities", [])) > 0
        )
    print(f"  LLM unavailable -> deterministic fallback: {'PASS' if llm_pass else 'FAIL'}")

    # 2. Database Failure (MongoDB unreachable)
    with patch("app.api.corpus.get_db", side_effect=RuntimeError("MongoDB connection lost")):
        r_db = client.get("/api/corpus/stats")
        db_pass = r_db.status_code == 500 and "Unable to load corpus data." in r_db.json().get("detail", "")
    print(f"  MongoDB unreachable -> safe HTTP 500: {'PASS' if db_pass else 'FAIL'}")

    # 3. Geocoding Failure (timeout/network error)
    _GEOCODE_CACHE.clear()
    with patch("httpx.Client.get", side_effect=httpx.TimeoutException("Nominatim timed out")):
        geo_res = geocode_location("Jaipur", timeout_sec=0.1)
        loc_ent = {"id": "ent_test_g", "name": "Jaipur", "entity_type": "LOCATION", "metadata": {}}
        enriched = enrich_entity_with_geocoding(loc_ent)
        geo_pass = (
            geo_res.get("status") == "unavailable"
            and enriched["metadata"].get("geocoding_status") == "unknown"
        )
    print(f"  Geocoding timeout -> graceful degradation: {'PASS' if geo_pass else 'FAIL'}")

    # 4. Network Timeout Handling
    with patch("httpx.Client.post", side_effect=httpx.TimeoutException("LLM post timeout")):
        gemini_res = call_gemini_api("Prompt text", api_key="test_key")
        net_pass = gemini_res is None
    print(f"  Network timeout -> safe graceful handling: {'PASS' if net_pass else 'FAIL'}")

    return llm_pass, db_pass, geo_pass, net_pass


def main() -> int:
    print("=" * 60)
    print("NEXUS TASK 8.1 — COMPREHENSIVE AUTOMATED VERIFICATION")
    print("=" * 60)

    # 1. Curated cases
    curated_pass = test_curated_cases()

    # 2. Boundary inputs
    empty_pass, short_pass, single_pass, multi_pass = test_boundary_inputs()

    # 3. Failure simulations
    llm_pass, db_pass, geo_pass, net_pass = test_failure_simulations()

    # 4. Provenance Integrity
    print("\n[4/5] Executing Strict MongoDB Provenance Integrity Query...")
    db = get_db()
    missing_entities, missing_edges, total_invalid = verify_provenance_integrity(db)
    prov_pass = total_invalid == 0
    print(f"  Missing entity provenance: {missing_entities}")
    print(f"  Missing edge provenance:   {missing_edges}")
    print(f"  TOTAL INVALID PROVENANCE: {total_invalid}")
    print(f"  Provenance Integrity:      {'PASS' if prov_pass else 'FAIL'}")

    print("\n" + "=" * 60)
    print("TASK 8.1 VERIFICATION SUMMARY")
    print("=" * 60)
    print(f"Curated cases:       {'PASS' if curated_pass else 'FAIL'}")
    print(f"Empty input:         {'PASS' if empty_pass else 'FAIL'}")
    print(f"Short input:         {'PASS' if short_pass else 'FAIL'}")
    print(f"Single accused:      {'PASS' if single_pass else 'FAIL'}")
    print(f"LLM fallback:        {'PASS' if llm_pass else 'FAIL'}")
    print(f"DB failure:          {'PASS' if db_pass else 'FAIL'}")
    print(f"Geocoding failure:   {'PASS' if geo_pass else 'FAIL'}")
    print(f"Network timeout:     {'PASS' if net_pass else 'FAIL'}")
    print(f"Provenance integrity:{'PASS' if prov_pass else 'FAIL'}")
    print(f"Missing provenance:  {total_invalid}")
    print("=" * 60)

    all_passed = all([
        curated_pass,
        empty_pass,
        short_pass,
        single_pass,
        multi_pass,
        llm_pass,
        db_pass,
        geo_pass,
        net_pass,
        prov_pass,
    ])

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
