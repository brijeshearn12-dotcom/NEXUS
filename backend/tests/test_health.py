"""Tests for /health and /health/db endpoints and CORS configuration."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app

PROD_FRONTEND_ORIGIN = "https://nexus-frontend-qtak.onrender.com"


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_db():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/db")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"


@pytest.mark.asyncio
async def test_cors_production_frontend_get():
    """Verify CORS headers on GET /health and /health/db from production frontend origin."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_health = await client.get("/health", headers={"Origin": PROD_FRONTEND_ORIGIN})
        assert res_health.status_code == 200
        assert res_health.headers.get("access-control-allow-origin") == PROD_FRONTEND_ORIGIN
        assert res_health.headers.get("access-control-allow-credentials") == "true"

        res_db = await client.get("/health/db", headers={"Origin": PROD_FRONTEND_ORIGIN})
        assert res_db.status_code == 200
        assert res_db.headers.get("access-control-allow-origin") == PROD_FRONTEND_ORIGIN
        assert res_db.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.asyncio
async def test_cors_options_preflight():
    """Verify CORS OPTIONS preflight request handling for /health and /health/db."""
    preflight_headers = {
        "Origin": PROD_FRONTEND_ORIGIN,
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "accept",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Preflight for /health
        res_preflight_health = await client.options("/health", headers=preflight_headers)
        assert res_preflight_health.status_code == 200
        assert res_preflight_health.headers.get("access-control-allow-origin") == PROD_FRONTEND_ORIGIN
        assert "GET" in res_preflight_health.headers.get("access-control-allow-methods", "")

        # Preflight for /health/db
        res_preflight_db = await client.options("/health/db", headers=preflight_headers)
        assert res_preflight_db.status_code == 200
        assert res_preflight_db.headers.get("access-control-allow-origin") == PROD_FRONTEND_ORIGIN
        assert "GET" in res_preflight_db.headers.get("access-control-allow-methods", "")


@pytest.mark.asyncio
async def test_cors_localhost_origins():
    """Verify local development origins are permitted."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res1 = await client.get("/health", headers={"Origin": "http://localhost:3000"})
        assert res1.status_code == 200
        assert res1.headers.get("access-control-allow-origin") == "http://localhost:3000"

        res2 = await client.get("/health", headers={"Origin": "http://127.0.0.1:3000"})
        assert res2.status_code == 200
        assert res2.headers.get("access-control-allow-origin") == "http://127.0.0.1:3000"


@pytest.mark.asyncio
async def test_cors_disallowed_origin():
    """Verify unallowed origins do NOT receive CORS allow-origin headers."""
    disallowed = "https://unauthorized-malicious-site.com"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/health", headers={"Origin": disallowed})
        assert res.status_code == 200
        assert "access-control-allow-origin" not in res.headers

        res_opt = await client.options(
            "/health",
            headers={"Origin": disallowed, "Access-Control-Request-Method": "GET"},
        )
        assert "access-control-allow-origin" not in res_opt.headers


def test_cors_no_wildcard_in_production():
    """Verify wildcard '*' is not present in allowed CORS origins."""
    assert "*" not in settings.allowed_cors_origins
    assert PROD_FRONTEND_ORIGIN in settings.allowed_cors_origins

