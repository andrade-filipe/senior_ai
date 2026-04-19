"""Shared pytest fixtures for transpiler tests.

spec_example_dict is a literal copy of the spec.example.json block
from docs/ARCHITECTURE.md § "Schema Pydantic do JSON spec".

Snapshot tests (test_snapshots.py) use pytest-regressions. On first run,
data files are created and the tests pass once with --gen-files. On
subsequent runs, they compare against the committed snapshot files.
"""

from typing import Any

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "snapshot: mark test as a snapshot test (requires --force-regen on first run)",
    )


@pytest.fixture
def spec_example_dict() -> dict[str, Any]:
    """Return the canonical example spec as a plain dict.

    Copied verbatim from docs/ARCHITECTURE.md § "Schema Pydantic do JSON spec"
    spec.example.json block. Must not be edited without also updating
    ARCHITECTURE.md — these two must stay in sync.
    """
    return {
        "name": "medical-order-agent",
        "description": "Agente de agendamento de exames a partir de pedidos médicos",
        "model": "gemini-2.5-flash",
        "instruction": "Você recebe uma imagem...",
        "mcp_servers": [
            {"name": "ocr", "url": "http://ocr-mcp:8001/sse"},
            {"name": "rag", "url": "http://rag-mcp:8002/sse"},
        ],
        "http_tools": [
            {
                "name": "scheduling",
                "base_url": "http://scheduling-api:8000",
                "openapi_url": "http://scheduling-api:8000/openapi.json",
            }
        ],
        "guardrails": {"pii": {"enabled": True, "allow_list": []}},
    }
