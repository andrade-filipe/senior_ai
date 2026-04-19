"""Tests for appointment CRUD endpoints (AC3–AC6, AC9, AC11–AC14, AC17).

Tasks: T012, T013, T014, T015, T018, T033, T034, T035, T036, T039.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest


# ---------------------------------------------------------------------------
# AC3 — happy path create (T012 [DbC])
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_returns_201_with_canonical_shape(async_client, sample_create_payload):
    """[AC3][DbC] POST returns 201 with all required fields (T012)."""
    response = await async_client.post("/api/v1/appointments", json=sample_create_payload)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "scheduled"
    assert "id" in body
    assert body["id"].startswith("apt-")
    assert "created_at" in body
    assert body["patient_ref"] == "anon-abc123"
    assert len(body["exams"]) == 2
    # Location header required (plan.md DbC)
    assert "location" in response.headers
    assert response.headers["location"].startswith("/api/v1/appointments/apt-")


# ---------------------------------------------------------------------------
# AC4 — missing required fields (T013)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_body_missing_patient_ref_returns_422(async_client, sample_create_payload):
    """[AC4] POST without patient_ref returns 422 with E_API_VALIDATION."""
    payload = dict(sample_create_payload)
    del payload["patient_ref"]
    response = await async_client.post("/api/v1/appointments", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "E_API_VALIDATION"
    assert "detail" not in body


@pytest.mark.asyncio
async def test_invalid_body_empty_exams_returns_422(async_client, sample_create_payload):
    """[AC4] POST with empty exams returns 422 with E_API_VALIDATION."""
    payload = dict(sample_create_payload)
    payload["exams"] = []
    response = await async_client.post("/api/v1/appointments", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "E_API_VALIDATION"


# ---------------------------------------------------------------------------
# AC5 — get by ID and 404 (T014)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_by_id_200_and_404(async_client, sample_create_payload):
    """[AC5] GET /{id} returns 200 for existing, 404 for missing."""
    create_resp = await async_client.post("/api/v1/appointments", json=sample_create_payload)
    assert create_resp.status_code == 201
    appt_id = create_resp.json()["id"]

    # 200 for existing
    get_resp = await async_client.get(f"/api/v1/appointments/{appt_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == appt_id

    # 404 for non-existing
    not_found = await async_client.get("/api/v1/appointments/apt-nonexistent")
    assert not_found.status_code == 404
    body = not_found.json()
    assert body["error"]["code"] == "E_API_NOT_FOUND"
    assert "detail" not in body


# ---------------------------------------------------------------------------
# AC6 — list pagination (T015)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_pagination(async_client, sample_create_payload):
    """[AC6] GET /appointments returns items and total."""
    # Create 3 appointments
    for _ in range(3):
        r = await async_client.post("/api/v1/appointments", json=sample_create_payload)
        assert r.status_code == 201

    response = await async_client.get("/api/v1/appointments?limit=10&offset=0")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3
    assert body["limit"] == 10
    assert body["offset"] == 0


@pytest.mark.asyncio
async def test_list_pagination_offset(async_client, sample_create_payload):
    """[AC6] Pagination offset works correctly."""
    for _ in range(5):
        r = await async_client.post("/api/v1/appointments", json=sample_create_payload)
        assert r.status_code == 201

    response = await async_client.get("/api/v1/appointments?limit=2&offset=2")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2


# ---------------------------------------------------------------------------
# AC9 — patient_ref pattern (T018 [DbC])
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_anon_patient_ref_rejected_422(async_client, sample_create_payload):
    """[AC9][DbC] POST with non-anon patient_ref returns 422 (T018)."""
    payload = dict(sample_create_payload)
    payload["patient_ref"] = "João Silva"  # raw PII-like name
    response = await async_client.post("/api/v1/appointments", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "E_API_VALIDATION"


@pytest.mark.asyncio
async def test_patient_ref_with_uppercase_rejected(async_client, sample_create_payload):
    """[AC9] patient_ref must be all lowercase alphanumeric after 'anon-'."""
    payload = dict(sample_create_payload)
    payload["patient_ref"] = "anon-ABC123"
    response = await async_client.post("/api/v1/appointments", json=payload)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# AC11 — notes cap 500 chars (T033 [DbC])
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notes_over_500_chars_rejected(async_client, sample_create_payload):
    """[AC11][DbC] POST with notes > 500 chars returns 422 citando notes (T033)."""
    payload = dict(sample_create_payload)
    payload["notes"] = "a" * 501
    response = await async_client.post("/api/v1/appointments", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "E_API_VALIDATION"
    # path should mention 'notes'
    path = body["error"].get("path", "") or ""
    context = body["error"].get("context", {}) or {}
    errors = context.get("errors", [])
    error_locs = [str(e.get("loc", "")) for e in errors]
    assert any("notes" in loc for loc in error_locs), f"notes not in error locs: {error_locs}"


@pytest.mark.asyncio
async def test_notes_exactly_500_chars_accepted(async_client, sample_create_payload):
    """[AC11] notes == 500 chars is accepted."""
    payload = dict(sample_create_payload)
    payload["notes"] = "b" * 500
    response = await async_client.post("/api/v1/appointments", json=payload)
    assert response.status_code == 201


# ---------------------------------------------------------------------------
# AC12 — scheduled_for in past (T034 [DbC])
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scheduled_for_in_past_rejected(async_client, sample_create_payload):
    """[AC12][DbC] POST with scheduled_for yesterday returns 422 (T034)."""
    payload = dict(sample_create_payload)
    past = datetime.now(timezone.utc) - timedelta(days=1)
    payload["scheduled_for"] = past.isoformat()
    response = await async_client.post("/api/v1/appointments", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "E_API_VALIDATION"


@pytest.mark.asyncio
async def test_scheduled_for_naive_rejected(async_client, sample_create_payload):
    """[AC12] naive datetime (no timezone) returns 422."""
    payload = dict(sample_create_payload)
    payload["scheduled_for"] = "2099-01-01T09:00:00"  # no tz info
    response = await async_client.post("/api/v1/appointments", json=payload)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# AC13 — exams > 20 items (T035 [DbC])
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exams_over_20_items_rejected(async_client, sample_create_payload):
    """[AC13][DbC] POST with 21 exams returns 422 (T035)."""
    payload = dict(sample_create_payload)
    payload["exams"] = [{"name": f"Exam {i}", "code": f"EX-{i:03}"} for i in range(21)]
    response = await async_client.post("/api/v1/appointments", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "E_API_VALIDATION"


@pytest.mark.asyncio
async def test_exams_exactly_20_items_accepted(async_client, sample_create_payload):
    """[AC13] 20 exams is within cap and accepted."""
    payload = dict(sample_create_payload)
    payload["exams"] = [{"name": f"Exam {i}", "code": f"EX-{i:03}"} for i in range(20)]
    response = await async_client.post("/api/v1/appointments", json=payload)
    assert response.status_code == 201


# ---------------------------------------------------------------------------
# AC14 — query param caps (T036 [DbC])
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pagination_caps_limit_over_100(async_client):
    """[AC14][DbC] limit=101 returns 422 (T036)."""
    response = await async_client.get("/api/v1/appointments?limit=101")
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "E_API_VALIDATION"


@pytest.mark.asyncio
async def test_pagination_caps_limit_zero(async_client):
    """[AC14] limit=0 returns 422."""
    response = await async_client.get("/api/v1/appointments?limit=0")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_pagination_caps_negative_offset(async_client):
    """[AC14] offset=-1 returns 422."""
    response = await async_client.get("/api/v1/appointments?offset=-1")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# AC17 — notes PII rejection (T039 [DbC])
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notes_with_cpf_rejected(async_client, sample_create_payload):
    """[AC17][DbC] POST with CPF in notes returns 422 (T039)."""
    payload = dict(sample_create_payload)
    payload["notes"] = "meu CPF é 111.444.777-35"
    response = await async_client.post("/api/v1/appointments", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "E_API_VALIDATION"


@pytest.mark.asyncio
async def test_notes_with_email_rejected(async_client, sample_create_payload):
    """[AC17] POST with email in notes returns 422."""
    payload = dict(sample_create_payload)
    payload["notes"] = "meu email é paciente@example.com"
    response = await async_client.post("/api/v1/appointments", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "E_API_VALIDATION"


@pytest.mark.asyncio
async def test_notes_without_pii_accepted(async_client, sample_create_payload):
    """[AC17] notes without PII patterns is accepted."""
    payload = dict(sample_create_payload)
    payload["notes"] = "Paciente em jejum de 8h. Exame de rotina."
    response = await async_client.post("/api/v1/appointments", json=payload)
    assert response.status_code == 201
