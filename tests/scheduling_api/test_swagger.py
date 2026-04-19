"""Tests for Swagger UI availability (AC2) — T011."""

import pytest


@pytest.mark.asyncio
async def test_docs_ui_available(async_client):
    """[AC2] GET /docs returns 200 HTML page."""
    response = await async_client.get("/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_openapi_has_post_route(async_client):
    """[AC2] GET /openapi.json includes POST /api/v1/appointments."""
    response = await async_client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    paths = spec.get("paths", {})
    assert "/api/v1/appointments" in paths
    assert "post" in paths["/api/v1/appointments"]
