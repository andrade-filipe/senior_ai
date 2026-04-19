"""FastAPI application factory with middleware stack and exception handlers.

Middleware order (outermost → innermost):
  1. TimeoutMiddleware      — hard 10 s per-request timeout (AC15)
  2. BodySizeLimitMiddleware — reject body > 256 KB before Pydantic (AC10)
  3. CorrelationIdMiddleware — X-Correlation-ID propagation + JSON logging (AC7)

Exception handlers override FastAPI defaults so ALL 4xx/5xx use the
canonical ADR-0008 shape: {error: {code, message, hint, path, context},
correlation_id} — never ``{"detail": ...}`` (AC16).
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .errors import (
    E_API_INTERNAL,
    E_API_PAYLOAD_TOO_LARGE,
    E_API_TIMEOUT,
    E_API_VALIDATION,
    make_error_envelope,
)
from .logging_ import CorrelationIdMiddleware, correlation_id_var
from .routes.appointments import router as appointments_router
from .routes.health import router as health_router

# ---------------------------------------------------------------------------
# Body size limit middleware (AC10)
# ---------------------------------------------------------------------------

BODY_SIZE_LIMIT_BYTES: int = 256 * 1024  # 256 KB


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests whose Content-Length exceeds BODY_SIZE_LIMIT_BYTES.

    Pre  — request arrives before Pydantic parsing (middleware chain position).
    Post — 413 with code=E_API_PAYLOAD_TOO_LARGE when limit exceeded.
    Invariant — body never reaches route handler if Content-Length > limit.

    Note: relies on Content-Length header. Clients without Content-Length
    are NOT blocked here (would require streaming body inspection — out of scope
    for MVP). This covers the primary threat vector (spec AC10).
    """

    def __init__(self, app: ASGIApp, max_bytes: int = BODY_SIZE_LIMIT_BYTES) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next: Any) -> JSONResponse:  # type: ignore[override]
        """Check Content-Length before forwarding the request."""
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                size = int(content_length)
            except ValueError:
                size = 0
            if size > self.max_bytes:
                cid = correlation_id_var.get("unknown")
                envelope = make_error_envelope(
                    code=E_API_PAYLOAD_TOO_LARGE,
                    message=f"Body excede o limite de {self.max_bytes // 1024} KB",
                    correlation_id=cid,
                    hint="Reduza o tamanho do payload. Limite: 256 KB.",
                    context={"received_bytes": size, "max_bytes": self.max_bytes},
                )
                return JSONResponse(
                    status_code=413,
                    content=envelope.model_dump(),
                    headers={"X-Correlation-ID": cid},
                )
        return await call_next(request)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Timeout middleware (AC15)
# ---------------------------------------------------------------------------

REQUEST_TIMEOUT_SECONDS: float = 10.0


class TimeoutMiddleware(BaseHTTPMiddleware):
    """Hard per-request timeout (AC15, ADR-0008 § Timeouts).

    Post — 504 with code=E_API_TIMEOUT when handler exceeds configured timeout.

    Implementation note: plain `asyncio.wait_for` cancels the handler task on
    expiry. `asyncio.shield` is intentionally NOT used — it would prevent
    cancellation and leak the task past the timeout.
    """

    def __init__(self, app: ASGIApp, timeout: float = REQUEST_TIMEOUT_SECONDS) -> None:
        super().__init__(app)
        self.timeout = timeout

    async def dispatch(self, request: Request, call_next: Any) -> Any:  # type: ignore[override]
        """Wrap handler in asyncio.wait_for; return 504 on TimeoutError."""
        try:
            return await asyncio.wait_for(
                call_next(request),
                timeout=self.timeout,
            )
        except (asyncio.TimeoutError, TimeoutError):
            cid = correlation_id_var.get("unknown")
            envelope = make_error_envelope(
                code=E_API_TIMEOUT,
                message=f"API não respondeu em {int(self.timeout)} s",
                correlation_id=cid,
                hint="Verifique se scheduling-api está saudável",
            )
            return JSONResponse(
                status_code=504,
                content=envelope.model_dump(),
                headers={"X-Correlation-ID": cid},
            )


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    Post: app has middleware stack + routers + exception handlers installed.
    """
    application = FastAPI(
        title="Scheduling API",
        version="1.0.0",
        description=(
            "API de agendamento de exames. Parte do Desafio Técnico Sênior IA. "
            "Consome payload canônico do agente ADK gerado (ver docs/ARCHITECTURE.md). "
            "Todos os campos PII são anonimizados upstream antes de chegar aqui (ADR-0003)."
        ),
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    # --- Middleware stack (outermost first) ---
    application.add_middleware(TimeoutMiddleware, timeout=REQUEST_TIMEOUT_SECONDS)
    application.add_middleware(BodySizeLimitMiddleware, max_bytes=BODY_SIZE_LIMIT_BYTES)
    application.add_middleware(CorrelationIdMiddleware)

    # --- Routers ---
    application.include_router(health_router)
    application.include_router(appointments_router)

    # --- Exception handlers (AC16) ---
    _register_exception_handlers(application)

    return application


def _register_exception_handlers(application: FastAPI) -> None:
    """Install canonical error shape handlers for all 4xx/5xx (AC16).

    Post: no response ever carries FastAPI's default ``{"detail": ...}`` shape.
    """

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Map Pydantic validation errors to E_API_VALIDATION (AC4, AC16)."""
        cid = correlation_id_var.get("unknown")
        errors = exc.errors()
        # Extract first error's location as path
        first = errors[0] if errors else {}
        loc = first.get("loc", ())
        path = ".".join(str(p) for p in loc) if loc else None
        context: dict[str, Any] = {"errors": [{"loc": e.get("loc"), "msg": e.get("msg")} for e in errors]}
        envelope = make_error_envelope(
            code=E_API_VALIDATION,
            message=first.get("msg", "Erro de validação"),
            correlation_id=cid,
            hint="Consulte /docs para o contrato da API",
            path=path,
            context=context,
        )
        return JSONResponse(
            status_code=422,
            content=envelope.model_dump(),
            headers={"X-Correlation-ID": cid},
        )

    @application.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        """Re-serialise HTTPException to canonical shape (AC16).

        When detail is already an ErrorEnvelope dict (from route handlers),
        preserve it; otherwise wrap it.
        """
        cid = correlation_id_var.get("unknown")
        detail = exc.detail

        # If our route handler raised HTTPException with an ErrorEnvelope dict, pass it through
        if isinstance(detail, dict) and "error" in detail and "correlation_id" in detail:
            return JSONResponse(
                status_code=exc.status_code,
                content=detail,
                headers={"X-Correlation-ID": cid},
            )

        # Generic HTTPException — wrap in canonical shape
        code = E_API_VALIDATION if exc.status_code == 422 else E_API_INTERNAL
        envelope = make_error_envelope(
            code=code,
            message=str(detail) if detail else f"HTTP {exc.status_code}",
            correlation_id=cid,
            hint="Consulte /docs para o contrato da API",
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=envelope.model_dump(),
            headers={"X-Correlation-ID": cid},
        )

    @application.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Catch-all for unexpected server errors (AC16).

        Post: 500 with canonical shape; error message does not leak internals.
        """
        cid = correlation_id_var.get("unknown")
        envelope = make_error_envelope(
            code=E_API_INTERNAL,
            message="Erro interno do servidor",
            correlation_id=cid,
            hint="Verifique os logs do serviço",
        )
        return JSONResponse(
            status_code=500,
            content=envelope.model_dump(),
            headers={"X-Correlation-ID": cid},
        )


# Module-level app instance (imported by __main__ and tests)
app: FastAPI = create_app()
