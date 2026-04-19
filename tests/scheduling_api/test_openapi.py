"""Tests for OpenAPI spec validity (AC8) — T017."""

import pytest


@pytest.mark.asyncio
async def test_openapi_json_parseable(async_client):
    """[AC8] GET /openapi.json returns valid OpenAPI 3.x spec (T017)."""
    response = await async_client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()

    # Must be valid OpenAPI structure
    assert "openapi" in spec
    assert spec["openapi"].startswith("3.")
    assert "info" in spec
    assert "paths" in spec


@pytest.mark.asyncio
async def test_openapi_post_has_request_body(async_client):
    """[AC8] POST /api/v1/appointments has requestBody in OpenAPI spec."""
    response = await async_client.get("/openapi.json")
    spec = response.json()
    post_op = spec["paths"]["/api/v1/appointments"]["post"]
    assert "requestBody" in post_op


@pytest.mark.asyncio
async def test_openapi_has_all_required_paths(async_client):
    """[AC2, AC8] OpenAPI spec includes all required endpoint paths."""
    response = await async_client.get("/openapi.json")
    spec = response.json()
    paths = spec["paths"]

    assert "/api/v1/appointments" in paths
    assert "/api/v1/appointments/{id}" in paths
    assert "/health" in paths
