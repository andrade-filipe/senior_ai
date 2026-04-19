"""Tests for correlation ID middleware (AC7) — T016 [DbC]."""

import pytest


@pytest.mark.asyncio
async def test_correlation_id_generated_when_absent(async_client):
    """[AC7][DbC] X-Correlation-ID generated and echoed when absent (T016)."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    assert "x-correlation-id" in response.headers
    cid = response.headers["x-correlation-id"]
    assert cid.startswith("api-"), f"Expected generated ID to start with 'api-', got: {cid}"


@pytest.mark.asyncio
async def test_correlation_id_echoed_when_provided(async_client):
    """[AC7] Provided X-Correlation-ID is echoed in response."""
    custom_cid = "my-request-abc123"
    response = await async_client.get("/health", headers={"X-Correlation-ID": custom_cid})
    assert response.status_code == 200
    assert response.headers.get("x-correlation-id") == custom_cid


@pytest.mark.asyncio
async def test_correlation_id_present_on_error_response(async_client):
    """[AC7] X-Correlation-ID present on error responses."""
    response = await async_client.get("/api/v1/appointments/nonexistent-id")
    assert response.status_code == 404
    assert "x-correlation-id" in response.headers


@pytest.mark.asyncio
async def test_correlation_id_in_error_body(async_client):
    """[AC7][AC16] Error body includes correlation_id field."""
    response = await async_client.get("/api/v1/appointments/nonexistent-id")
    body = response.json()
    assert "correlation_id" in body
    assert body["correlation_id"] is not None
