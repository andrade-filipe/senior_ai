"""Tests for GET /health (AC1) — T010."""

import pytest


@pytest.mark.asyncio
async def test_health_returns_ok(async_client):
    """[AC1] GET /health returns 200 with status='ok'."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body == {"status": "ok"}
