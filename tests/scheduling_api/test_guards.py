"""Tests for body size limit (AC10) and timeout (AC15) — T029, T037 [DbC]."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from scheduling_api.app import (
    BODY_SIZE_LIMIT_BYTES,
    BodySizeLimitMiddleware,
    TimeoutMiddleware,
    _register_exception_handlers,
)
from scheduling_api.logging_ import CorrelationIdMiddleware


# ---------------------------------------------------------------------------
# AC10 — body size limit (T029 [DbC])
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_body_size_limit_413(async_client):
    """[AC10][DbC] POST with Content-Length > 256 KB returns 413 (T029).

    Sends a body of 300 KB; BodySizeLimitMiddleware intercepts via Content-Length
    header before Pydantic ever runs.
    """
    large_size = 300 * 1024  # 300 KB
    large_body = b"x" * large_size
    response = await async_client.post(
        "/api/v1/appointments",
        content=large_body,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    body = response.json()
    assert body["error"]["code"] == "E_API_PAYLOAD_TOO_LARGE"
    assert "detail" not in body


@pytest.mark.asyncio
async def test_body_within_limit_reaches_pydantic(async_client):
    """[AC10] Valid-size body with invalid payload returns 422 (Pydantic ran, not 413)."""
    invalid_payload = {"patient_ref": "anon-xyz"}  # missing exams
    response = await async_client.post("/api/v1/appointments", json=invalid_payload)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# AC15 — timeout (T037 [DbC])
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_endpoint_timeout_504():
    """[AC15][DbC] Handler exceeding timeout returns 504 with E_API_TIMEOUT (T037).

    Builds an isolated FastAPI app with a 1-second TimeoutMiddleware and a
    slow endpoint that sleeps 3 seconds, verifying the 504 response shape.
    """
    test_app = FastAPI()
    test_app.add_middleware(TimeoutMiddleware, timeout=1.0)
    test_app.add_middleware(BodySizeLimitMiddleware, max_bytes=BODY_SIZE_LIMIT_BYTES)
    test_app.add_middleware(CorrelationIdMiddleware)
    _register_exception_handlers(test_app)

    @test_app.post("/slow")
    async def slow_endpoint() -> dict:
        await asyncio.sleep(3)  # exceeds 1s timeout
        return {"id": "never-reached"}

    transport = ASGITransport(app=test_app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/slow", json={}, timeout=10.0)

    assert response.status_code == 504
    body = response.json()
    assert body["error"]["code"] == "E_API_TIMEOUT"
    assert "detail" not in body
