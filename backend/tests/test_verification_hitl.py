"""
Tests for Task 6.1 — Human-in-the-Loop Verification Endpoints and Persistence.
"""
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import get_db
from app.main import app


@pytest.mark.asyncio
async def test_entity_verification_lifecycle():
    """Verify entity confirmation, rejection, and audit trail in MongoDB."""
    db = get_db()
    test_entity_id = "test_ent_hitl_001"

    # Seed test entity
    db.entities.delete_one({"id": test_entity_id})
    db.entities.insert_one({
        "id": test_entity_id,
        "name": "Arun Kumar",
        "entity_type": "PERSON",
        "verification_status": "unverified",
        "case_id": "case_100478559",
        "provenance": {
            "tier": "primary",
            "source_ref": "FIR-2019-88",
            "method": "spacy",
            "confidence": 0.88,
        },
    })

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. GET initial status
        get_res = await client.get(f"/api/entities/{test_entity_id}/verify")
        assert get_res.status_code == 200
        get_json = get_res.json()
        assert get_json["entity_id"] == test_entity_id
        assert get_json["verification_status"] == "unverified"

        # 2. PATCH to confirmed
        patch_res = await client.patch(
            f"/api/entities/{test_entity_id}/verify",
            json={
                "verification_status": "confirmed",
                "analyst_id": "senior_analyst_1",
                "notes": "Corroborated by High Court witness testimony",
            },
        )
        assert patch_res.status_code == 200
        patch_json = patch_res.json()
        assert patch_json["status"] == "ok"
        assert patch_json["verification_status"] == "confirmed"

        # 3. GET to verify persistence
        get_after = await client.get(f"/api/entities/{test_entity_id}/verify")
        assert get_after.status_code == 200
        assert get_after.json()["verification_status"] == "confirmed"

        # Verify audit log recorded in MongoDB
        audit_entry = db.audit_log.find_one({"entity_id": test_entity_id, "verification_status": "confirmed"})
        assert audit_entry is not None
        assert audit_entry["actor"] == "senior_analyst_1"

        # 4. PATCH to rejected
        reject_res = await client.patch(
            f"/api/entities/{test_entity_id}/verify",
            json={
                "verification_status": "rejected",
                "analyst_id": "senior_analyst_1",
                "notes": "Witness mistook common name",
            },
        )
        assert reject_res.status_code == 200
        assert reject_res.json()["verification_status"] == "rejected"

        # Verify entity was NOT deleted, but status is rejected
        ent_doc = db.entities.find_one({"id": test_entity_id})
        assert ent_doc is not None
        assert ent_doc["verification_status"] == "rejected"

    # Cleanup
    db.entities.delete_one({"id": test_entity_id})
    db.audit_log.delete_many({"entity_id": test_entity_id})


@pytest.mark.asyncio
async def test_flag_verification_lifecycle():
    """Verify case pattern flag confirmation and persistence across analysis calls."""
    db = get_db()
    test_case_id = "test_case_hitl_flags"
    test_flag_id = "flag_test_bridge_001"

    # Seed test flag
    db.flags.delete_one({"flag_id": test_flag_id})
    db.flags.insert_one({
        "flag_id": test_flag_id,
        "case_id": test_case_id,
        "flag_type": "bridge_node",
        "entity_id": "ent_test_99",
        "canonical_name": "Test Facilitator",
        "severity": "high",
        "description": "Critical bridge between two criminal syndicates",
        "verification_status": "unverified",
    })

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. PATCH to confirmed
        patch_res = await client.patch(
            f"/api/cases/{test_case_id}/flags/{test_flag_id}/verify",
            json={
                "verification_status": "confirmed",
                "analyst_id": "intelligence_officer_2",
                "notes": "Verified bridge actor through financial records",
            },
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["verification_status"] == "confirmed"

        # 2. Check persistence in MongoDB
        flag_doc = db.flags.find_one({"flag_id": test_flag_id})
        assert flag_doc is not None
        assert flag_doc["verification_status"] == "confirmed"

        # 3. Check audit log in MongoDB
        audit_doc = db.audit_log.find_one({"entity_id": test_flag_id, "verification_status": "confirmed"})
        assert audit_doc is not None
        assert audit_doc["actor"] == "intelligence_officer_2"

    # Cleanup
    db.flags.delete_one({"flag_id": test_flag_id})
    db.audit_log.delete_many({"entity_id": test_flag_id})
