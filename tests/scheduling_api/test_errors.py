"""Tests for canonical error response shape (AC16) — T038 [DbC]."""

import pytest


CANONICAL_ERROR_KEYS = {"code", "message", "hint", "path", "context"}


@pytest.mark.asyncio
async def test_validation_error_has_canonical_shape(async_client):
    """[AC16][DbC] 422 from invalid body uses canonical shape (T038)."""
    response = await async_client.post("/api/v1/appointments", json={"patient_ref": "invalid"})
    assert response.status_code == 422
    body = response.json()

    # Must have 'error' and 'correlation_id' at top level
    assert "error" in body, f"'error' key missing in: {body}"
    assert "correlation_id" in body, f"'correlation_id' key missing in: {body}"
    # Must NOT have 'detail' (FastAPI default)
    assert "detail" not in body, f"'detail' key present (FastAPI default leaked): {body}"

    error = body["error"]
    assert "code" in error
    assert "message" in error
    # All canonical keys present (hint/path/context may be None but key exists)
    for key in ("code", "message"):
        assert key in error, f"'{key}' missing in error: {error}"


@pytest.mark.asyncio
async def test_not_found_error_has_canonical_shape(async_client):
    """[AC16][DbC] 404 from missing resource uses canonical shape (T038)."""
    response = await async_client.get("/api/v1/appointments/nonexistent-apt")
    assert response.status_code == 404
    body = response.json()

    assert "error" in body
    assert "correlation_id" in body
    assert "detail" not in body

    error = body["error"]
    assert error["code"] == "E_API_NOT_FOUND"
    assert "message" in error


@pytest.mark.asyncio
async def test_error_code_never_uses_fastapi_default(async_client):
    """[AC16] All error responses avoid FastAPI's detail key."""
    # Test 422 (validation)
    r422 = await async_client.post("/api/v1/appointments", json={})
    assert r422.status_code == 422
    assert "detail" not in r422.json()

    # Test 404 (not found)
    r404 = await async_client.get("/api/v1/appointments/fake-id")
    assert r404.status_code == 404
    assert "detail" not in r404.json()
