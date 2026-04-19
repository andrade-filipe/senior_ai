"""Transpiler package: JSON spec → ADK Python package.

Public API surface for the transpiler module. Consumers should import
from here rather than from sub-modules directly.

Exports:
    AgentSpec       — Root Pydantic model for the transpiler input spec.
    McpServerSpec   — MCP server connection definition.
    HttpToolSpec    — HTTP service definition.
    PiiGuardSpec    — PII guardrail configuration.
    GuardrailSpec   — Container for guardrail policies.
    load_spec       — Load and validate an AgentSpec from file path or dict.
    TranspilerError — Exception raised by the transpiler module.
    ChallengeError  — Base exception for all challenge services.
    format_challenge_error — Serialize a ChallengeError to canonical dict shape.
    render          — Render an AgentSpec to a generated_agent/ package.
"""

from transpiler.errors import ChallengeError, TranspilerError, format_challenge_error
from transpiler.generator import render
from transpiler.schema import (
    AgentSpec,
    GuardrailSpec,
    HttpToolSpec,
    McpServerSpec,
    PiiGuardSpec,
    load_spec,
)

__all__ = [
    "AgentSpec",
    "McpServerSpec",
    "HttpToolSpec",
    "PiiGuardSpec",
    "GuardrailSpec",
    "load_spec",
    "TranspilerError",
    "ChallengeError",
    "format_challenge_error",
    "render",
]
