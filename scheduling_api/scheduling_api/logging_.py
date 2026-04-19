"""Structured JSON logging and correlation ID middleware.

Provides:
  - ``correlation_id_var``: ContextVar holding the request correlation ID.
  - ``CorrelationIdMiddleware``: Starlette middleware that reads or generates
    ``X-Correlation-ID`` and echoes it in the response (AC7, ADR-0008 § 5).
  - ``JsonFormatter``: logging.Formatter that emits one JSON line per record
    with the mandatory fields from docs/ARCHITECTURE.md § "Formato de log".

Design by Contract (plan.md § CorrelationIdMiddleware):
  Invariant — ``X-Correlation-ID`` header present in 100 % of responses.
  Post      — ``correlation_id_var`` populated before handler executes.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextvars import ContextVar
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

# ContextVar shared by logger and route handlers
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="unknown")


class JsonFormatter(logging.Formatter):
    """Emit log records as single-line JSON (docs/ARCHITECTURE.md § Formato de log).

    Mandatory fields: ts, level, service, correlation_id, event, message.
    Optional extras surfaced via ``extra`` keyword in log calls.
    Never logs PII (ADR-0003, GUIDELINES § 3).
    """

    SERVICE = "scheduling-api"

    def format(self, record: logging.LogRecord) -> str:
        """Serialize record to JSON string.

        Post: output is valid JSON; correlation_id always present.
        """
        payload: dict[str, object] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S.") + f"{record.msecs:03.0f}Z",
            "level": record.levelname,
            "service": self.SERVICE,
            "correlation_id": correlation_id_var.get("unknown"),
            "event": getattr(record, "event", "log"),
            "message": record.getMessage(),
        }
        # Forward any extra keys (never PII — caller's responsibility)
        for key, val in record.__dict__.items():
            if key not in {
                "args", "created", "exc_info", "exc_text", "filename", "funcName",
                "levelname", "levelno", "lineno", "message", "module", "msecs",
                "msg", "name", "pathname", "process", "processName", "relativeCreated",
                "stack_info", "thread", "threadName", "event",
            }:
                if not key.startswith("_"):
                    payload[key] = val
        return json.dumps(payload, default=str, ensure_ascii=False)


def _setup_logger() -> logging.Logger:
    """Create and configure the scheduling-api root logger.

    Post: logger emits JSON to stdout; no duplicate handlers on re-import.
    """
    logger = logging.getLogger("scheduling_api")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


logger: logging.Logger = _setup_logger()


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Read or generate X-Correlation-ID; populate ContextVar; echo in response.

    Pre: request is an HTTP request (any path/method).
    Post: response always includes X-Correlation-ID header.
    Invariant: correlation_id_var populated for the lifetime of the request.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:  # type: ignore[override]
        """Assign correlation ID and log http.request with duration_ms (AC7)."""
        raw = request.headers.get("X-Correlation-ID")
        cid = raw if raw else f"api-{uuid.uuid4().hex[:8]}"
        token = correlation_id_var.set(cid)

        start = time.monotonic()
        try:
            response: Response = await call_next(request)
            duration_ms = round((time.monotonic() - start) * 1000, 2)
            # Emit log while the ContextVar is still set — JsonFormatter reads
            # correlation_id_var at serialization time, so reset must come after.
            logger.info(
                "http.request",
                extra={
                    "event": "http.request",
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
            response.headers["X-Correlation-ID"] = cid
            return response
        finally:
            correlation_id_var.reset(token)
