"""JSON structured logging for RAG MCP (ADR-0008 § Formato de log).

Identical structure to ocr_mcp/logging_.py — both will be unified in Block 8
if a shared library is introduced. For now each service owns its copy.

Log format (one JSON per line on stderr):
    {ts, level, service, event, extra, correlation_id?}

The `event` field is the first positional arg to the logger call (e.g. "tool.called").
Reserved LogRecord attributes (msg, message, args, filename, ...) never land in `extra` —
we collect only the caller-provided keys to avoid overwriting stdlib fields.

PII rule (ADR-0008 § Logging sem PII crua):
    Never pass raw PII values. Only entity_type, sha256_prefix, counts, durations.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

_RESERVED_LOGRECORD_FIELDS: frozenset[str] = frozenset({
    "args", "asctime", "created", "exc_info", "exc_text", "filename",
    "funcName", "levelname", "levelno", "lineno", "message", "module",
    "msecs", "msg", "name", "pathname", "process", "processName",
    "relativeCreated", "stack_info", "thread", "threadName", "taskName",
})


class _JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON."""

    def __init__(self, service: str) -> None:
        super().__init__()
        self._service = service

    def format(self, record: logging.LogRecord) -> str:
        extra: dict[str, Any] = {
            k: v
            for k, v in record.__dict__.items()
            if k not in _RESERVED_LOGRECORD_FIELDS
        }
        correlation_id = extra.pop("correlation_id", None)
        record_dict: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S.%f"
            )[:-3]
            + "Z",
            "level": record.levelname,
            "service": self._service,
            "event": record.getMessage(),
            "extra": extra,
        }
        if correlation_id is not None:
            record_dict["correlation_id"] = correlation_id
        return json.dumps(record_dict, ensure_ascii=False)


def get_logger(service: str = "rag-mcp") -> logging.Logger:
    """Return a logger that emits single-line JSON to stderr.

    Args:
        service: Service name written in every log record's ``service`` field.

    Returns:
        Configured stdlib Logger instance.
    """
    logger = logging.getLogger(service)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(_JsonFormatter(service))
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
    return logger
