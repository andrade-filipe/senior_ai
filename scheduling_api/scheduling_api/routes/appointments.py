"""Appointment CRUD endpoints.

Routes:
  POST /api/v1/appointments — create (AC3, AC9, AC11, AC12, AC13, AC17)
  GET  /api/v1/appointments/{id} — read by ID (AC5)
  GET  /api/v1/appointments — paginated list (AC6, AC14)

Design by Contract (plan.md § POST /api/v1/appointments):
  Pre  — body matches AppointmentCreate (exams non-empty; patient_ref anon pattern;
         body ≤ 256 KB enforced by BodySizeLimitMiddleware upstream).
  Post — 201 with Appointment; Location header set; error shape canonical (ADR-0008).
  Invariant — Location header points to /api/v1/appointments/{id} (plan.md DbC).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from ..errors import E_API_NOT_FOUND, make_error_envelope
from ..logging_ import correlation_id_var
from ..models import Appointment, AppointmentCreate, AppointmentList
from ..repository import AppointmentRepository, InMemoryAppointmentRepository, generate_appointment_id

router = APIRouter(prefix="/api/v1", tags=["appointments"])

# ---------------------------------------------------------------------------
# Dependency injection — allows tests to swap repository
# ---------------------------------------------------------------------------

# Module-level default repository; tests override via dependency_overrides
_default_repo: InMemoryAppointmentRepository = InMemoryAppointmentRepository()


def get_repository() -> AppointmentRepository:
    """Return the active appointment repository.

    Post: always returns a valid AppointmentRepository instance.
    """
    return _default_repo


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/appointments",
    response_model=Appointment,
    status_code=201,
    summary="Criar agendamento",
    description=(
        "Cria um novo agendamento. "
        "`patient_ref` deve seguir o padrão `anon-[a-z0-9]+` (PII-zero). "
        "`scheduled_for` deve ser data/hora futura com timezone. "
        "Body máximo: 256 KB."
    ),
    responses={
        201: {"description": "Agendamento criado"},
        413: {"description": "Body > 256 KB"},
        422: {"description": "Validação falhou"},
        504: {"description": "Timeout"},
    },
)
async def create_appointment(
    payload: AppointmentCreate,
    request: Request,
    response: Response,
    repo: AppointmentRepository = Depends(get_repository),
) -> Appointment:
    """Create and store a new appointment.

    Pre  — payload validated by Pydantic (AC3, AC9, AC11, AC12, AC13, AC17).
    Post — 201; Location header; appointment persisted and retrievable.
    """
    appt = Appointment(
        id=generate_appointment_id(),
        status="scheduled",
        created_at=datetime.now(timezone.utc),
        patient_ref=payload.patient_ref,
        exams=payload.exams,
        scheduled_for=payload.scheduled_for,
        notes=payload.notes,
    )
    repo.add(appt)
    response.headers["Location"] = f"/api/v1/appointments/{appt.id}"
    return appt


@router.get(
    "/appointments/{id}",
    response_model=Appointment,
    summary="Buscar agendamento por ID",
    responses={
        200: {"description": "Agendamento encontrado"},
        404: {"description": "Agendamento não encontrado"},
    },
)
async def get_appointment(
    id: str,
    request: Request,
    repo: AppointmentRepository = Depends(get_repository),
) -> Appointment:
    """Return appointment by ID or 404 (AC5).

    Pre:  id is a non-empty string.
    Post: 200 + Appointment, or 404 with canonical error shape.
    """
    appt = repo.get(id)
    if appt is None:
        cid = correlation_id_var.get("unknown")
        envelope = make_error_envelope(
            code=E_API_NOT_FOUND,
            message=f"Agendamento '{id}' não encontrado",
            correlation_id=cid,
            hint="Confirme o ID do agendamento",
            path="path.id",
        )
        raise HTTPException(
            status_code=404,
            detail=envelope.model_dump(),
        )
    return appt


@router.get(
    "/appointments",
    response_model=AppointmentList,
    summary="Listar agendamentos",
    description="Lista paginada de agendamentos. `limit` deve estar entre 1 e 100; `offset` ≥ 0.",
    responses={
        200: {"description": "Lista paginada"},
        422: {"description": "Query params inválidos"},
    },
)
async def list_appointments(
    limit: int = Query(default=10, ge=1, le=100, description="Número de itens por página (1–100)"),
    offset: int = Query(default=0, ge=0, description="Número de itens a pular"),
    repo: AppointmentRepository = Depends(get_repository),
) -> AppointmentList:
    """Return paginated appointment list (AC6, AC14).

    Pre  — limit ∈ [1, 100], offset ≥ 0 (enforced by Query validators).
    Post — items ≤ limit; total reflects full store count.
    """
    items, total = repo.list_all(limit=limit, offset=offset)
    return AppointmentList(items=items, total=total, limit=limit, offset=offset)
