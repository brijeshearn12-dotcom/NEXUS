"""Task 8.2 — input-size limits and clean error responses.

Oversized input is rejected with a clean 4xx before any database work; realistic input still
reaches the endpoint (a 404 for an unknown ID proves validation passed).
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.limits import (
    MAX_ID_LIST_ITEMS,
    MAX_NOTES_CHARS,
    MAX_QUERY_TEXT_CHARS,
    MAX_REQUEST_BODY_BYTES,
    MAX_TITLE_CHARS,
    MAX_URL_PATH_CHARS,
    safe_error_detail,
)
from app.main import app

client = TestClient(app)


def test_declared_oversized_body_is_rejected_with_413():
    resp = client.post(
        "/api/cases/case_x/ingest",
        content=b"{}",
        headers={"content-type": "application/json", "content-length": str(MAX_REQUEST_BODY_BYTES + 1)},
    )
    assert resp.status_code == 413
    assert "limit" in resp.json()["detail"]


def test_streamed_oversized_body_is_rejected_with_413():
    def chunks():
        block = b"x" * (1024 * 1024)
        for _ in range(MAX_REQUEST_BODY_BYTES // len(block) + 2):
            yield block

    resp = client.post("/api/cases/case_x/ingest", content=chunks(), headers={"content-type": "application/json"})
    assert resp.status_code == 413


def test_overlong_url_is_rejected_with_414():
    resp = client.get("/api/entities/" + "a" * (MAX_URL_PATH_CHARS + 10))
    assert resp.status_code == 414


def test_overlong_notes_are_rejected_with_422():
    resp = client.patch("/api/entities/ent_x/verify", json={"status": "confirmed", "notes": "n" * (MAX_NOTES_CHARS + 1)})
    assert resp.status_code == 422


def test_overlong_search_query_is_rejected_with_422():
    resp = client.get("/api/entities", params={"q": "q" * (MAX_QUERY_TEXT_CHARS + 1)})
    assert resp.status_code == 422


def test_overlong_title_is_rejected_with_422():
    resp = client.post("/api/cases/case_x/ingest", json={"text": "Some judgment text.", "title": "t" * (MAX_TITLE_CHARS + 1)})
    assert resp.status_code == 422


def test_oversized_simulation_node_list_is_rejected_with_422():
    resp = client.post("/api/cases/case_x/simulate", json={"exclude_node_ids": ["n"] * (MAX_ID_LIST_ITEMS + 1)})
    assert resp.status_code == 422


def test_wrong_types_and_malformed_json_are_clean_4xx():
    assert client.post("/api/cases/case_x/simulate", json={"exclude_node_ids": "not-a-list"}).status_code == 422
    resp = client.post("/api/cases/case_x/simulate", content=b"{not json", headers={"content-type": "application/json"})
    assert resp.status_code == 422


def test_realistic_input_still_passes_validation():
    # Notes at the limit and a normal search reach the endpoint (unknown entity -> 404, not 422).
    resp = client.patch("/api/entities/ent_unknown/verify", json={"status": "confirmed", "notes": "n" * MAX_NOTES_CHARS})
    assert resp.status_code == 404
    assert client.get("/api/entities", params={"q": "Ramesh Kumar"}).status_code == 200


def test_internal_errors_do_not_leak_exception_text():
    secret_like = "cluster0-shard-00-01.example.mongodb.net:27017 timed out"
    with patch("app.api.documents.extract_and_store_document", side_effect=RuntimeError(secret_like)):
        resp = client.post("/api/documents/doc_x/extract")
    assert resp.status_code == 500
    assert secret_like not in resp.json()["detail"]
    assert "RuntimeError" in resp.json()["detail"]
    assert safe_error_detail("X", ValueError("boom")) == "X (ValueError). Details were recorded in the server log."
