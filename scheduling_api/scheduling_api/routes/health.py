"""Health check endpoint.

GET /health — liveness/readiness probe (AC1).
Used by Dockerfile HEALTHCHECK and docker-compose ``condition: service_healthy``.
"""

from fastapi import APIRouter

from ..models import HealthResponse

router = APIRouter(tags=["ops"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness / readiness probe",
    status_code=200,
)
async def health() -> HealthResponse:
    """Return service status.

    Post: always returns 200 with status="ok" in < 10 ms without touching state.
    """
    return HealthResponse(status="ok")
