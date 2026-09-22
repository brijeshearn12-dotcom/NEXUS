"""Automated unit and integration tests for Task 4.1 — Entity Alias Resolution.

Tests:
1. Exact same name
2. Whitespace and case differences
3. Minor spelling variation
4. Initials (positive and negative)
5. Different people with similar names (given-name guardrail)
6. Incompatible entity types
7. Blocking (reduces pair space, excludes disjoint names)
8. Threshold behavior
9. Idempotency (repeated runs do not duplicate merges)
10. Additive merge storage (original entities untouched, complete merge schema)
11. API response (POST /api/cases/{case_id}/resolve)
12. Real-corpus validation (2 true variants merge, 2 false matches do NOT merge)
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.models.enums import VerificationStatus
from app.services.resolution.alias_resolver import (
    are_types_compatible,
    check_initials_match,
    compute_similarity,
    get_blocking_keys,
    normalize_alias_name,
    resolve_case_aliases,
    select_canonical_entity,
)

client = TestClient(app)


# ── 1. NORMALIZATION TESTS ───────────────────────────────────────────────────


def test_normalize_name_whitespace_and_case():
    raw1 = "   Rajesh    Kumar   "
    raw2 = "rajesh kumar"
    raw3 = "RAJESH KUMAR"
    assert normalize_alias_name(raw1) == "rajesh kumar"
    assert normalize_alias_name(raw2) == "rajesh kumar"
    assert normalize_alias_name(raw3) == "rajesh kumar"


def test_normalize_name_punctuation_and_possessive():
    assert normalize_alias_name("Atiq Ahmad's") == "atiq ahmad"
    assert normalize_alias_name("Atiq Ahmad’s") == "atiq ahmad"
    assert normalize_alias_name("R.K. Sharma") == "r k sharma"
    assert normalize_alias_name("A-1 Rajesh Kumar") == "a 1 rajesh kumar"


def test_normalize_name_honorific_stripping():
    assert normalize_alias_name("Mr. Rajesh Kumar") == "rajesh kumar"
    assert normalize_alias_name("Dr. Anil Verma") == "anil verma"
    assert normalize_alias_name("Shri Narendra Modi") == "narendra modi"
    assert normalize_alias_name("Smt. Indira Gandhi") == "indira gandhi"


# ── 2. TYPE COMPATIBILITY TESTS ──────────────────────────────────────────────


def test_compatible_entity_types():
    assert are_types_compatible("PERSON", "PERSON") is True
    assert are_types_compatible("person", "PERSON") is True
    assert are_types_compatible("PERSON", "ACCUSED") is True
    assert are_types_compatible("ACCUSED", "PERSON") is True
    assert are_types_compatible("ORGANIZATION", "ORGANIZATION") is True
    assert are_types_compatible("LOCATION", "LOCATION") is True
    assert are_types_compatible("VEHICLE", "VEHICLE") is True


def test_incompatible_entity_types():
    assert are_types_compatible("PERSON", "LOCATION") is False
    assert are_types_compatible("PERSON", "ORGANIZATION") is False
    assert are_types_compatible("PERSON", "VEHICLE") is False
    assert are_types_compatible("LOCATION", "ORGANIZATION") is False
    assert are_types_compatible("PHONE", "FIR") is False


# ── 3. SIMILARITY & RESOLUTION RULES TESTS ────────────────────────────────────


def test_exact_same_name_resolution():
    sim, method = compute_similarity("Rajesh Kumar", "Rajesh Kumar")
    assert sim == 1.0
    assert method == "exact_match"


def test_whitespace_and_case_differences():
    sim, method = compute_similarity("  Mr. Rajesh   Kumar  ", "rajesh kumar")
    assert sim == 1.0
    assert method == "exact_match"


def test_minor_spelling_variation():
    # Atiq Ahmad vs Atiq Ahmed
    sim1, method1 = compute_similarity("Atiq Ahmad", "Atiq Ahmed")
    assert sim1 >= 0.85
    assert "rapidfuzz" in method1

    # Manish Goel vs Manish Goyal
    sim2, method2 = compute_similarity("Manish Goel", "Manish Goyal")
    assert sim2 >= 0.85
    assert "rapidfuzz" in method2


def test_initials_matching():
    # Positive: initial matches first letter of full name with matching surname
    sim1, method1 = compute_similarity("R. Kumar", "Rajesh Kumar")
    assert sim1 >= 0.85
    assert method1 == "initials_match"

    # Multi-initial match
    assert check_initials_match(["a", "k", "sharma"], ["anil", "kumar", "sharma"]) is True
    assert check_initials_match(["a", "sharma"], ["anil", "kumar", "sharma"]) is True

    # Negative: conflicting initials
    assert check_initials_match(["s", "kumar"], ["rajesh", "kumar"]) is False
    sim_neg, method_neg = compute_similarity("S. Kumar", "Rajesh Kumar")
    assert sim_neg < 0.85 or method_neg != "initials_match"


def test_different_people_with_similar_names():
    # Shared surname but completely different given names
    sim1, method1 = compute_similarity("Kaish Ahmad", "Atiq Ahmad")
    assert sim1 == 0.0
    assert method1 == "different_given_names"

    sim2, method2 = compute_similarity("Rajesh Kumar", "Suresh Kumar")
    assert sim2 == 0.0
    assert method2 == "different_given_names"

    sim3, method3 = compute_similarity("Prasad Singh", "Raghavendra Singh")
    assert sim3 == 0.0
    assert method3 == "different_given_names"

    # Different father/surname
    sim4, _ = compute_similarity("Kaish Ahmad", "Kaish Mohammad")
    assert sim4 < 0.85


def test_numeric_consistency_guardrail():
    # Different numbers/citations must never merge
    sim1, method1 = compute_similarity("FIR No. 123/2021", "FIR No. 456/2021")
    assert sim1 == 0.0
    assert method1 == "numeric_mismatch"

    sim2, method2 = compute_similarity("Crime No. 10/2020", "Crime No. 20/2020")
    assert sim2 == 0.0
    assert method2 == "numeric_mismatch"

    # Same numbers with formatting differences should merge
    sim3, _ = compute_similarity("Crime No. 693", "Crime No: 693")
    assert sim3 >= 0.85


def test_blocking_logic():
    # Tokens with shared 3-character prefixes share a block
    keys1 = get_blocking_keys("rajesh kumar")
    keys2 = get_blocking_keys("rajesh k")
    assert len(keys1.intersection(keys2)) > 0

    # Totally disjoint names share no blocks
    keys_a = get_blocking_keys("vikram malhotra")
    keys_b = get_blocking_keys("suresh raina")
    assert len(keys_a.intersection(keys_b)) == 0


def test_threshold_behavior():
    name1 = "Ramesh Gupta"
    name2 = "Ramesh Verma"  # Different surnames, Gupta vs Verma
    sim, _ = compute_similarity(name1, name2)
    # Conservative threshold 0.85 rejects this pair
    assert sim < 0.85


def test_select_canonical_entity():
    e_short = {
        "id": "ent_short",
        "name": "R. Kumar",
        "provenance": {"confidence": 0.85},
        "metadata": {"occurrence_count": 1},
    }
    e_full = {
        "id": "ent_full",
        "name": "Rajesh Kumar",
        "provenance": {"confidence": 0.95},
        "metadata": {"occurrence_count": 3},
    }
    canonical, alias = select_canonical_entity(e_short, e_full)
    assert canonical["id"] == "ent_full"
    assert alias["id"] == "ent_short"


# ── 4. INTEGRATION & STORAGE TESTS (SYNTHETIC MOCK CASE) ──────────────────────


@pytest.fixture
def mock_case_in_db():
    db = get_db()
    case_id = f"case_test_resolution_{uuid.uuid4().hex[:8]}"

    # Insert test case record
    db.cases.insert_one({"case_id": case_id, "title": "Test Resolution Case"})

    # Insert entities for this case
    entities = [
        # Pair 1: Minor spelling variation (should merge)
        {
            "id": f"ent_{case_id}_atiq1",
            "case_id": case_id,
            "document_id": "doc_test_1",
            "name": "Atiq Ahmad",
            "entity_type": "PERSON",
            "aliases": [],
            "provenance": {"confidence": 0.90, "source_ref": "doc_test_1", "method": "spacy_ner"},
            "verification_status": "unverified",
        },
        {
            "id": f"ent_{case_id}_atiq2",
            "case_id": case_id,
            "document_id": "doc_test_2",
            "name": "Atiq Ahmed",
            "entity_type": "PERSON",
            "aliases": [],
            "provenance": {"confidence": 0.90, "source_ref": "doc_test_2", "method": "spacy_ner"},
            "verification_status": "unverified",
        },
        # Pair 2: Different people sharing surname (should NOT merge)
        {
            "id": f"ent_{case_id}_kaish",
            "case_id": case_id,
            "document_id": "doc_test_1",
            "name": "Kaish Ahmad",
            "entity_type": "PERSON",
            "aliases": [],
            "provenance": {"confidence": 0.90, "source_ref": "doc_test_1", "method": "spacy_ner"},
            "verification_status": "unverified",
        },
        # Incompatible entity type: LOCATION with same prefix (should NOT merge with PERSON)
        {
            "id": f"ent_{case_id}_atiq_loc",
            "case_id": case_id,
            "document_id": "doc_test_1",
            "name": "Atiq Market",
            "entity_type": "LOCATION",
            "aliases": [],
            "provenance": {"confidence": 0.85, "source_ref": "doc_test_1", "method": "spacy_ner"},
            "verification_status": "unverified",
        },
        # Disjoint name (blocked out, 0 candidate pairs with Atiq)
        {
            "id": f"ent_{case_id}_vikram",
            "case_id": case_id,
            "document_id": "doc_test_1",
            "name": "Vikram Malhotra",
            "entity_type": "PERSON",
            "aliases": [],
            "provenance": {"confidence": 0.85, "source_ref": "doc_test_1", "method": "spacy_ner"},
            "verification_status": "unverified",
        },
    ]

    db.entities.insert_many(entities)

    yield case_id

    # Clean up test artifacts
    db.cases.delete_one({"case_id": case_id})
    db.entities.delete_many({"case_id": case_id})
    db.entity_merges.delete_many({"case_id": case_id})
    db.audit_log.delete_many({"case_id": case_id})


def test_additive_merge_storage_and_schema(mock_case_in_db: str):
    case_id = mock_case_in_db
    db = get_db()

    # Pre-condition: original entities count
    orig_entities_count = db.entities.count_documents({"case_id": case_id})
    assert orig_entities_count == 5

    stats = resolve_case_aliases(case_id, threshold=0.85, database=db)

    # 1. Atiq Ahmad and Atiq Ahmed merged
    assert stats["merges_created"] == 1
    assert stats["entities_checked"] == 5

    # 2. Never delete original entity: count must be strictly identical
    post_entities_count = db.entities.count_documents({"case_id": case_id})
    assert post_entities_count == orig_entities_count

    # 3. Check entity_merges collection schema
    merges = list(db.entity_merges.find({"case_id": case_id}))
    assert len(merges) == 1
    m = merges[0]

    # Verify all required schema fields
    assert "merge_id" in m
    assert m["merge_id"].startswith(f"merge_{case_id}_")
    assert "canonical_entity_id" in m
    assert "alias_entity_id" in m
    assert m["case_id"] == case_id
    assert 0.0 <= m["similarity_score"] <= 1.0
    assert 0.0 <= m["confidence"] <= 1.0
    assert m["method"] in {"exact_match", "initials_match", "rapidfuzz_token_sort", "rapidfuzz_ratio"}
    assert m["verification_status"] in {
        VerificationStatus.UNVERIFIED.value,
        VerificationStatus.CONFIRMED.value,
    }
    assert "created_at" in m
    assert isinstance(m["source_refs"], list)
    assert len(m["source_refs"]) >= 1


def test_idempotency_of_resolution(mock_case_in_db: str):
    case_id = mock_case_in_db
    db = get_db()

    # First run
    stats1 = resolve_case_aliases(case_id, threshold=0.85, database=db)
    merges_count_1 = db.entity_merges.count_documents({"case_id": case_id})

    # Second run
    stats2 = resolve_case_aliases(case_id, threshold=0.85, database=db)
    merges_count_2 = db.entity_merges.count_documents({"case_id": case_id})

    # Stats and DB state must be completely idempotent without duplicating records
    assert stats1["merges_created"] == stats2["merges_created"]
    assert stats1["candidate_pairs"] == stats2["candidate_pairs"]
    assert merges_count_1 == merges_count_2 == 1


# ── 5. API ENDPOINT TESTS ────────────────────────────────────────────────────


def test_api_case_resolve_endpoint(mock_case_in_db: str):
    case_id = mock_case_in_db

    response = client.post(f"/api/cases/{case_id}/resolve?threshold=0.85")
    assert response.status_code == 200
    data = response.json()

    assert data["case_id"] == case_id
    assert data["entities_checked"] == 5
    assert data["candidate_pairs"] >= 1
    assert data["merges_created"] == 1
    assert data["merges_skipped"] >= 1


def test_api_case_resolve_nonexistent():
    response = client.post("/api/cases/case_nonexistent_xyz_999/resolve")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ── 6. REAL CORPUS VERIFICATION TESTS ─────────────────────────────────────────


def test_real_corpus_true_variants_and_false_matches():
    """Verify on real NEXUS corpus:

    1. True variant 1: 'Atiq Ahmad' vs 'Atiq Ahmed' in case_141720225 -> MUST MERGE
    2. True variant 2: 'Manish Goel' vs 'Manish Goyal' in case_141720225 -> MUST MERGE
    3. False match 1: 'Kaish Ahmad' vs 'Kaish Mohammad' in case_141720225 -> MUST NOT MERGE
    4. False match 2: 'Kaish Ahmad' vs 'Atiq Ahmad' in case_141720225 -> MUST NOT MERGE
    """
    db = get_db()
    real_case_id = "case_141720225"

    # Check case exists in real MongoDB corpus
    if not db.entities.find_one({"case_id": real_case_id}):
        pytest.skip(f"Real case {real_case_id} not populated in MongoDB")

    # Run resolution on real case
    stats = resolve_case_aliases(real_case_id, threshold=0.85, database=db)
    assert stats["entities_checked"] >= 100
    assert stats["merges_created"] >= 2

    # Query merges created in DB
    merges = list(db.entity_merges.find({"case_id": real_case_id}))
    entities = {e["id"]: e for e in db.entities.find({"case_id": real_case_id})}

    resolved_pairs: set[tuple[str, str]] = set()
    for m in merges:
        c_name = entities[m["canonical_entity_id"]]["name"]
        a_name = entities[m["alias_entity_id"]]["name"]
        resolved_pairs.add(tuple(sorted([c_name, a_name])))

    # 1. True variant: Atiq Ahmad and Atiq Ahmed
    atiq_merged = any(
        {"Atiq Ahmad", "Atiq Ahmed"}.issubset(pair) or
        {"Atiq Ahmad's", "Atiq Ahmed"}.issubset(pair)
        for pair in resolved_pairs
    )
    assert atiq_merged is True, "Expected true variant (Atiq Ahmad / Atiq Ahmed) to be merged"

    # 2. True variant: Manish Goel and Manish Goyal
    manish_merged = any(
        {"Manish Goel", "Manish Goyal"}.issubset(pair)
        for pair in resolved_pairs
    )
    assert manish_merged is True, "Expected true variant (Manish Goel / Manish Goyal) to be merged"

    # 3. False match: Kaish Ahmad vs Kaish Mohammad (different father/surname)
    kaish_mohd_merged = any(
        {"Kaish Ahmad", "Kaish Mohammad"}.issubset(pair)
        for pair in resolved_pairs
    )
    assert kaish_mohd_merged is False, "False match Kaish Ahmad vs Kaish Mohammad should NOT be merged"

    # 4. False match: Kaish Ahmad vs Atiq Ahmad (different person, shared surname)
    kaish_atiq_merged = any(
        {"Kaish Ahmad", "Atiq Ahmad"}.issubset(pair)
        for pair in resolved_pairs
    )
    assert kaish_atiq_merged is False, "False match Kaish Ahmad vs Atiq Ahmad should NOT be merged"
