"""Pydantic v2 request/response models for the scheduling API.

Canonical payload shape is frozen by docs/ARCHITECTURE.md § "Agente → Scheduling API"
and ADR-0008 (caps, pattern constraints).

Design by Contract (plan.md § Design by Contract):
  Pre  — patient_ref matches ``^anon-[a-z0-9]+$``; scheduled_for is timezone-aware future;
         exams non-empty; notes ≤ 500 chars (AC9, AC11, AC12, AC13, AC17).
  Post — Appointment.id unique; status="scheduled"; created_at server-set.
  Invariant — patient_ref never holds raw PII; notes never matches PII patterns.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# PII defensive patterns (AC17, docs/ARCHITECTURE.md § "Lista definitiva de entidades PII")
# ---------------------------------------------------------------------------

# CPF: nnn.nnn.nnn-nn or nnnnnnnnnnn
_CPF_RE = re.compile(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}")
# E-mail (basic RFC-like)
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
# BR phone: (DDD) 9xxxx-xxxx or variations
_PHONE_RE = re.compile(r"(?:\+?55\s?)?(?:\(?\d{2}\)?[\s\-]?)(?:9\d{4}[\s\-]?\d{4}|\d{4}[\s\-]?\d{4})")

_PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("BR_CPF", _CPF_RE),
    ("EMAIL_ADDRESS", _EMAIL_RE),
    ("BR_PHONE", _PHONE_RE),
]


def _check_notes_pii(value: str) -> str:
    """Reject notes that match PII patterns (AC17, defensive layer).

    Pre: value is a non-empty string.
    Post: returns value unchanged if no PII detected.
    Raises: ValueError when any PII pattern matches.
    """
    for entity_type, pattern in _PII_PATTERNS:
        if pattern.search(value):
            raise ValueError(
                f"notes contém padrão PII detectado ({entity_type}). "
                "Remova dados pessoais antes de enviar. Consulte /docs para o contrato."
            )
    return value


# ---------------------------------------------------------------------------
# Shared type aliases
# ---------------------------------------------------------------------------

# patient_ref must be anonymised (AC9, plan.md § Design by Contract)
PatientRef = Annotated[str, Field(pattern=r"^anon-[a-z0-9]+$", max_length=64)]


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class ExamRef(BaseModel):
    """A resolved exam item with canonical name and code.

    Both fields are required and non-empty.
    """

    name: str = Field(..., min_length=1)
    code: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------


class AppointmentCreate(BaseModel):
    """Request body for POST /api/v1/appointments.

    Pre  — patient_ref matches anon pattern; exams non-empty (≤ 20);
           scheduled_for is future and timezone-aware; notes ≤ 500 chars.
    Post — fields validated by Pydantic; model_validator ensures scheduled_for > now().
    Invariant — notes never matches CPF/email/phone patterns (AC17).
    """

    patient_ref: PatientRef
    exams: list[ExamRef] = Field(..., min_length=1, max_length=20)
    # AwareDatetime rejects naive datetimes automatically (AC12, Pydantic v2)
    scheduled_for: AwareDatetime
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("notes")
    @classmethod
    def notes_no_pii(cls, v: str | None) -> str | None:
        """Reject notes containing PII patterns (AC17)."""
        if v is not None:
            return _check_notes_pii(v)
        return v

    @model_validator(mode="after")
    def scheduled_for_must_be_future(self) -> "AppointmentCreate":
        """Reject scheduled_for in the past (AC12).

        Pre: scheduled_for is timezone-aware (guaranteed by AwareDatetime type).
        Post: scheduled_for > now(UTC).
        """
        now = datetime.now(timezone.utc)
        if self.scheduled_for <= now:
            raise ValueError(
                "scheduled_for deve estar no futuro. "
                f"Valor recebido: {self.scheduled_for.isoformat()}"
            )
        return self


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class Appointment(BaseModel):
    """Full appointment resource returned by the API.

    Invariant — patient_ref matches anon pattern; notes has no PII.
    """

    id: str
    status: Literal["scheduled"]
    created_at: AwareDatetime
    patient_ref: PatientRef
    exams: list[ExamRef]
    scheduled_for: AwareDatetime
    notes: str | None = None


class AppointmentList(BaseModel):
    """Paginated list envelope for GET /api/v1/appointments (AC6)."""

    items: list[Appointment]
    total: int
    limit: int
    offset: int


class HealthResponse(BaseModel):
    """Response for GET /health (AC1)."""

    status: Literal["ok"]
