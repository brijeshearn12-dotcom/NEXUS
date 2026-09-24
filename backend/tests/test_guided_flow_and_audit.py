"""
Tests for Task 6.2 — Guided Analysis Flow Orchestration and Read-Only Audit Trail.
"""
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import get_db
from app.main import app


@pytest.mark.asyncio
async def test_guided_flow_and_audit_lifecycle():
    """Verify that extract -> resolve -> build-graph -> analysis -> audit produces authoritative entries."""
    case_id = "case_100478559"
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Extraction endpoint
        ext_res = await client.post(f"/api/cases/{case_id}/extract")
        assert ext_res.status_code == 200
        ext_json = ext_res.json()
        assert ext_json["status"] == "ok"
        assert ext_json["case_id"] == case_id

        # 2. Alias resolution endpoint
        res_res = await client.post(f"/api/cases/{case_id}/resolve")
        assert res_res.status_code == 200
        res_json = res_res.json()
        assert res_json["case_id"] == case_id
        assert "merges_created" in res_json

        # 3. Build graph endpoint
        bg_res = await client.post(f"/api/cases/{case_id}/build-graph")
        assert bg_res.status_code == 200
        bg_json = bg_res.json()
        assert bg_json["case_id"] == case_id
        assert "nodes" in bg_json

        # 4. Analysis calculation endpoint
        an_res = await client.get(f"/api/cases/{case_id}/analysis")
        assert an_res.status_code == 200
        an_json = an_res.json()
        assert an_json["status"] == "ok"
        assert len(an_json["ranked_individuals"]) > 0

        # 5. Read-only Audit Trail retrieval
        audit_res = await client.get(f"/api/cases/{case_id}/audit?limit=20")
        assert audit_res.status_code == 200
        audit_json = audit_res.json()
        assert audit_json["case_id"] == case_id
        assert audit_json["total"] > 0
        items = audit_json["items"]
        actions = [item["action"] for item in items]

        # Verify key authoritative events exist in the audit log
        assert any("analysis" in a or "extract" in a or "graph" in a or "alias" in a for a in actions)


@pytest.mark.asyncio
async def test_what_if_simulation_logs_audit():
    """Verify that what-if simulation records an audit entry and does not mutate graph."""
    case_id = "case_100478559"
    db = get_db()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Get baseline graph count
        g_before = await client.get(f"/api/cases/{case_id}/graph")
        assert g_before.status_code == 200
        orig_nodes = len(g_before.json()["nodes"])
        top_node_id = g_before.json()["nodes"][0]["id"]

        # Run simulation
        sim_res = await client.post(
            f"/api/cases/{case_id}/simulate",
            json={"exclude_node_ids": [top_node_id]},
        )
        assert sim_res.status_code == 200
        sim_json = sim_res.json()
        assert sim_json["status"] == "ok"
        assert top_node_id in sim_json["excluded_node_ids"]

        # Verify underlying graph in DB was NOT mutated
        g_after = await client.get(f"/api/cases/{case_id}/graph")
        assert len(g_after.json()["nodes"]) == orig_nodes, "Underlying MongoDB graph was mutated!"

        # Verify audit event was recorded
        sim_audit = db.audit_log.find_one({
            "case_id": case_id,
            "action": "what_if_simulation_executed",
        })
        assert sim_audit is not None
        assert sim_audit["actor"] == "analyst_simulation"
