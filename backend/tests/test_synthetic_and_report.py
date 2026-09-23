"""Unit and integration tests for Task 7.1: Synthetic CDR/Transaction Bridge and PDF Report Export."""

from __future__ import annotations

from httpx import ASGITransport, AsyncClient
import pytest

from app.core.db import get_db
from app.main import app
from app.services.report_generator import generate_case_pdf_report
from app.services.synthetic import (
    clear_case_synthetic_bridge,
    generate_case_synthetic_bridge,
    generate_synthetic_cdr,
    generate_synthetic_transactions,
    get_case_synthetic_summary,
)


@pytest.fixture
def setup_test_case():
    """Seed clean test case data into MongoDB for synthetic bridge and report tests."""
    db = get_db()
    case_id = "test_case_synth_71"

    # Clean up prior test runs
    db.cases.delete_one({"case_id": case_id})
    db.entities.delete_many({"case_id": case_id})
    db.edges.delete_many({"$or": [{"case_id": case_id}, {"case_ids": case_id}]})
    db.audit_log.delete_many({"case_id": case_id})

    # Seed test case
    db.cases.insert_one({
        "case_id": case_id,
        "title": "State of Maharashtra v. Syndicate 71",
        "description": "Multi-state organized financial crime investigation",
    })

    # Seed 4 real extracted entities
    entities = [
        {"id": "ent_p1_71", "case_id": case_id, "name": "Vikram Malhotra", "entity_type": "PERSON", "verification_status": "confirmed"},
        {"id": "ent_p2_71", "case_id": case_id, "name": "Sameer Khan", "entity_type": "PERSON", "verification_status": "unverified"},
        {"id": "ent_p3_71", "case_id": case_id, "name": "Anita Desai", "entity_type": "PERSON", "verification_status": "confirmed"},
        {"id": "ent_o1_71", "case_id": case_id, "name": "Global Horizon Ltd", "entity_type": "ORGANIZATION", "verification_status": "unverified"},
    ]
    db.entities.insert_many(entities)

    # Seed 2 primary evidence edges
    primary_edges = [
        {
            "id": "edge_real_1_71",
            "edge_id": "edge_real_1_71",
            "case_id": case_id,
            "case_ids": [case_id],
            "source_entity_id": "ent_p1_71",
            "target_entity_id": "ent_p2_71",
            "relationship_type": "co_accused",
            "edge_type": "co_accused",
            "weight": 2.0,
            "provenance": {"tier": "primary", "method": "direct_text", "source_ref": "FIR-402"},
            "verification_status": "confirmed",
        },
        {
            "id": "edge_real_2_71",
            "edge_id": "edge_real_2_71",
            "case_id": case_id,
            "case_ids": [case_id],
            "source_entity_id": "ent_p2_71",
            "target_entity_id": "ent_p3_71",
            "relationship_type": "associated_with",
            "edge_type": "associated_with",
            "weight": 1.5,
            "provenance": {"tier": "primary", "method": "direct_text", "source_ref": "Witness-01"},
            "verification_status": "unverified",
        },
    ]
    db.edges.insert_many(primary_edges)

    yield case_id

    # Teardown
    db.cases.delete_one({"case_id": case_id})
    db.entities.delete_many({"case_id": case_id})
    db.edges.delete_many({"$or": [{"case_id": case_id}, {"case_ids": case_id}]})
    db.audit_log.delete_many({"case_id": case_id})


def test_cdr_generator_connects_only_existing_entities(setup_test_case):
    """Ensure CDR generator connects strictly existing entities and does not invent new entities."""
    case_id = setup_test_case
    db = get_db()
    entities = list(db.entities.find({"case_id": case_id}))
    valid_ids = {e["id"] for e in entities}

    cdr_edges = generate_synthetic_cdr(case_id, entities, count=3)
    assert len(cdr_edges) == 3

    for edge in cdr_edges:
        assert edge["source_entity_id"] in valid_ids
        assert edge["target_entity_id"] in valid_ids
        assert edge["source_entity_id"] != edge["target_entity_id"]
        assert edge["relationship_type"] == "SYNTHETIC_CDR"
        assert edge["edge_type"] == "SYNTHETIC_CDR"
        assert edge["provenance"]["tier"] == "synthetic"
        assert edge["provenance"]["method"] == "faker"
        assert "SYNTHETIC DEMO" in edge["evidence"]


def test_transaction_generator_connects_only_existing_entities(setup_test_case):
    """Ensure transaction generator connects strictly existing entities and marks synthetic provenance."""
    case_id = setup_test_case
    db = get_db()
    entities = list(db.entities.find({"case_id": case_id}))
    valid_ids = {e["id"] for e in entities}

    txn_edges = generate_synthetic_transactions(case_id, entities, count=3)
    assert len(txn_edges) == 3

    for edge in txn_edges:
        assert edge["source_entity_id"] in valid_ids
        assert edge["target_entity_id"] in valid_ids
        assert edge["source_entity_id"] != edge["target_entity_id"]
        assert edge["relationship_type"] == "SYNTHETIC_TRANSACTION"
        assert edge["edge_type"] == "SYNTHETIC_TRANSACTION"
        assert edge["provenance"]["tier"] == "synthetic"
        assert edge["provenance"]["metadata"]["synthetic"] is True


def test_synthetic_bridge_lifecycle_and_audit(setup_test_case):
    """Test generating synthetic bridge, auditing, querying summary, and clearing."""
    case_id = setup_test_case
    db = get_db()

    # Initial summary
    initial_summary = get_case_synthetic_summary(case_id, database=db)
    assert initial_summary["total_edges"] == 2
    assert initial_summary["synthetic_edges"] == 0
    assert initial_summary["has_synthetic_data"] is False

    # Generate synthetic edges (3 CDR, 2 Txn)
    gen_result = generate_case_synthetic_bridge(
        case_id=case_id,
        cdr_count=3,
        transaction_count=2,
        database=db,
    )
    assert gen_result["status"] == "ok"
    assert gen_result["cdr_count"] == 3
    assert gen_result["transaction_count"] == 2
    assert gen_result["total_generated"] == 5

    # Check updated summary
    updated_summary = get_case_synthetic_summary(case_id, database=db)
    assert updated_summary["total_edges"] == 7
    assert updated_summary["synthetic_edges"] == 5
    assert updated_summary["primary_edges"] == 2
    assert updated_summary["synthetic_cdr_count"] == 3
    assert updated_summary["synthetic_transaction_count"] == 2
    assert updated_summary["has_synthetic_data"] is True

    # Verify audit log recorded generation
    audit_gen = db.audit_log.find_one({"action": "synthetic_data_generated", "case_id": case_id})
    assert audit_gen is not None
    assert audit_gen["actor"] == "system_synthetic_bridge"

    # Clear synthetic edges
    clear_result = clear_case_synthetic_bridge(case_id, database=db)
    assert clear_result["status"] == "ok"
    assert clear_result["deleted_count"] == 5

    # Verify baseline is fully restored
    restored_summary = get_case_synthetic_summary(case_id, database=db)
    assert restored_summary["total_edges"] == 2
    assert restored_summary["synthetic_edges"] == 0
    assert restored_summary["has_synthetic_data"] is False

    # Verify audit log recorded clearing
    audit_clear = db.audit_log.find_one({"action": "synthetic_data_cleared", "case_id": case_id})
    assert audit_clear is not None


def test_pdf_report_generation(setup_test_case):
    """Test generating full investigation PDF report."""
    case_id = setup_test_case
    db = get_db()

    pdf_bytes = generate_case_pdf_report(case_id, database=db)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 2000
    assert pdf_bytes.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_api_report_and_synthetic_endpoints(setup_test_case):
    """Integration test for HTTP API endpoints using AsyncClient."""
    case_id = setup_test_case

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Generate synthetic edges via POST
        res_gen = await client.post(
            f"/api/cases/{case_id}/synthetic/generate",
            json={"cdr_count": 2, "transaction_count": 2},
        )
        assert res_gen.status_code == 200
        data_gen = res_gen.json()
        assert data_gen["status"] == "ok"
        assert data_gen["total_generated"] == 4

        # 2. Get synthetic summary via GET
        res_sum = await client.get(f"/api/cases/{case_id}/synthetic/summary")
        assert res_sum.status_code == 200
        data_sum = res_sum.json()
        assert data_sum["synthetic_edges"] == 4

        # 3. Download report via /api/cases/{case_id}/report
        res_rep1 = await client.get(f"/api/cases/{case_id}/report")
        assert res_rep1.status_code == 200
        assert res_rep1.headers["content-type"] == "application/pdf"
        assert res_rep1.content.startswith(b"%PDF")

        # 4. Download report via /api/report/{case_id}
        res_rep2 = await client.get(f"/api/report/{case_id}")
        assert res_rep2.status_code == 200
        assert res_rep2.headers["content-type"] == "application/pdf"
        assert res_rep2.content.startswith(b"%PDF")

        # 5. Clear synthetic edges via DELETE
        res_del = await client.delete(f"/api/cases/{case_id}/synthetic")
        assert res_del.status_code == 200
        assert res_del.json()["deleted_count"] == 4
