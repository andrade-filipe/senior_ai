"""Shared pytest fixtures for scheduling_api tests (T003, T004).

Uses httpx.AsyncClient with ASGITransport — NOT the sync TestClient
(GUIDELINES § 4, plan.md § Estratégia de validação).

Each test module gets a fresh InMemoryAppointmentRepository via
dependency_overrides so tests are isolated.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from scheduling_api.app import app
from scheduling_api.repository import InMemoryAppointmentRepository
from scheduling_api.routes.appointments import get_repository


@pytest_asyncio.fixture()
async def async_client():
    """AsyncClient with a fresh in-memory repository per test (T003).

    Post: app.dependency_overrides cleared after test.
    """
    repo = InMemoryAppointmentRepository()
    app.dependency_overrides[get_repository] = lambda: repo

    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture()
def sample_create_payload() -> dict:
    """Valid AppointmentCreate payload for happy-path tests (T004).

    scheduled_for is set 7 days in the future to avoid AC12 failures.
    """
    future = datetime.now(timezone.utc) + timedelta(days=7)
    return {
        "patient_ref": "anon-abc123",
        "exams": [
            {"name": "Hemograma Completo", "code": "HMG-001"},
            {"name": "Glicemia de Jejum", "code": "GLC-001"},
        ],
        "scheduled_for": future.isoformat(),
        "notes": None,
    }
