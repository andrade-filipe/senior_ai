"""AgentSpec Pydantic schema and load_spec loader.

Frozen schema per ADR-0006. Any field addition requires a new ADR
superseding ADR-0006. Guardrails applied per ADR-0008.

Design by Contract summary (full table in docs/specs/0001-agentspec-schema/plan.md):
    AgentSpec.Invariant  — model in allowlist; mcp_servers/http_tools at least one non-empty;
                           list caps (10/20/50); string caps (500/2048 chars).
    McpServerSpec.Post   — url validated as AnyHttpUrl after construction.
    McpServerSpec.Invariant — name unique among siblings.
    load_spec.Pre        — file size ≤ 1 MB before json.loads.
    load_spec.Post       — returns a fully-validated AgentSpec.
    load_spec.Invariant  — round-trip model_dump_json() → load_spec() is stable.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, Literal

import pydantic
from pydantic import AnyHttpUrl, BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from transpiler.errors import TranspilerError, format_validation_error

# ---------------------------------------------------------------------------
# Annotated URL type with string-length cap (ADR-0008 — 2048 chars)
# ---------------------------------------------------------------------------
# AnyHttpUrl coerces to pydantic.Url; str(url) gives the string back.
# We validate the raw string length BEFORE Pydantic coerces the value so the
# cap check happens on the original input (borda check per ADR-0008).

_MAX_URL_LEN = 2048


def _validate_url_length(v: Any) -> Any:  # noqa: ANN401
    """Pre-coercion URL length check (ADR-0008 cap: 2048 chars).

    Pre:
        v is the raw input value (str or any type before AnyHttpUrl coercion).
    Post:
        Returns v unchanged if len(str(v)) ≤ 2048.
    Raises:
        ValueError if len(str(v)) > 2048.
    """
    if isinstance(v, str) and len(v) > _MAX_URL_LEN:
        raise ValueError(
            f"URL excede {_MAX_URL_LEN} caracteres (observado: {len(v)} chars). "
            f"Reduza a URL conforme o cap definido em ADR-0008."
        )
    return v


BoundedUrl = Annotated[
    AnyHttpUrl,
    BeforeValidator(_validate_url_length),
]

# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

_MAX_NAME_LEN = 500
_MAX_DESC_LEN = 500
_MAX_INSTRUCTION_LEN = 500
_MAX_MCP_SERVERS = 10
_MAX_HTTP_TOOLS = 20
_MAX_TOOL_FILTER = 50


class McpServerSpec(BaseModel):
    """MCP server connection definition.

    Invariant:
        name must be unique among siblings within the same AgentSpec (enforced
        by AgentSpec.model_validator).
        url must be a valid HTTP URL of at most 2048 chars (ADR-0008).

    Post:
        After construction, url is a validated AnyHttpUrl instance.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(
        pattern=r"^[a-z0-9][a-z0-9-]*$",
        max_length=_MAX_NAME_LEN,
        description="Unique identifier for this MCP server within the spec.",
    )
    url: BoundedUrl = Field(
        description="SSE endpoint URL of the MCP server (e.g. http://ocr-mcp:8001/sse).",
    )
    tool_filter: list[str] | None = Field(
        default=None,
        max_length=_MAX_TOOL_FILTER,
        description="Optional list of tool names to expose. None means all tools.",
    )


class HttpToolSpec(BaseModel):
    """HTTP service definition (non-MCP, typically a REST API).

    Post:
        After construction, base_url and openapi_url (if provided) are
        validated AnyHttpUrl instances of at most 2048 chars each.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(
        pattern=r"^[a-z0-9][a-z0-9-]*$",
        max_length=_MAX_NAME_LEN,
    )
    base_url: BoundedUrl = Field(
        description="Base URL of the HTTP service (e.g. http://scheduling-api:8000).",
    )
    openapi_url: BoundedUrl | None = Field(
        default=None,
        description="Optional OpenAPI spec URL for auto-generating tools.",
    )


class PiiGuardSpec(BaseModel):
    """PII guardrail configuration for the generated agent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = True
    allow_list: list[str] = Field(default_factory=list)


class GuardrailSpec(BaseModel):
    """Container for all guardrail policies attached to an AgentSpec."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pii: PiiGuardSpec = Field(default_factory=PiiGuardSpec)


# ---------------------------------------------------------------------------
# Root model
# ---------------------------------------------------------------------------


class AgentSpec(BaseModel):
    """Root schema for a transpiler input spec (ADR-0006, frozen).

    Invariant:
        - model must be 'gemini-2.5-flash' (ADR-0006 allowlist, ADR-0005).
        - name matches ^[a-z0-9][a-z0-9-]*$ and is ≤ 500 chars.
        - description and instruction are ≤ 500 chars.
        - At least one of mcp_servers, http_tools must be non-empty (AC5).
        - mcp_servers has at most 10 items; http_tools at most 20 items (ADR-0008).
        - mcp_servers[*].name is unique within this spec (AC9).
        - All URL fields are valid HTTP URLs of at most 2048 chars (ADR-0008).

    Any field addition requires a new ADR superseding ADR-0006.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(
        pattern=r"^[a-z0-9][a-z0-9-]*$",
        max_length=_MAX_NAME_LEN,
        description="Unique agent identifier. Used as Python package name in generated code.",
    )
    description: str = Field(
        max_length=_MAX_DESC_LEN,
        description="Short human-readable description of the agent.",
    )
    model: Literal["gemini-2.5-flash"] = Field(
        description="LLM model identifier. Literal forces a conscious ADR when changing models.",
    )
    instruction: str = Field(
        max_length=_MAX_INSTRUCTION_LEN,
        description="System prompt / instruction for the LlmAgent (imperative style).",
    )
    mcp_servers: list[McpServerSpec] = Field(
        default_factory=list,
        max_length=_MAX_MCP_SERVERS,
        description="MCP servers to connect. At most 10 entries (ADR-0008).",
    )
    http_tools: list[HttpToolSpec] = Field(
        default_factory=list,
        max_length=_MAX_HTTP_TOOLS,
        description="HTTP services to expose as tools. At most 20 entries (ADR-0008).",
    )
    guardrails: GuardrailSpec = Field(
        default_factory=GuardrailSpec,
        description="Guardrail policies for the generated agent.",
    )

    @model_validator(mode="after")
    def _check_invariants(self) -> "AgentSpec":
        """Enforce AgentSpec cross-field invariants (AC5, AC9).

        Invariant:
            - At least one of mcp_servers / http_tools must be non-empty (AC5).
            - mcp_servers[*].name must be unique (AC9).

        Raises:
            ValueError: when an invariant is violated.
        """
        # AC5: at least one source of tools
        if not self.mcp_servers and not self.http_tools:
            raise ValueError(
                "AgentSpec deve ter ao menos um item em 'mcp_servers' ou 'http_tools'. "
                "Um agente sem ferramentas não é útil."
            )

        # AC9: unique MCP server names
        seen: set[str] = set()
        for srv in self.mcp_servers:
            if srv.name in seen:
                raise ValueError(
                    f"Nome duplicado em mcp_servers: '{srv.name}'. "
                    f"Cada servidor MCP deve ter um 'name' único dentro do mesmo AgentSpec."
                )
            seen.add(srv.name)

        return self


# ---------------------------------------------------------------------------
# Public loader
# ---------------------------------------------------------------------------

_MAX_SPEC_BYTES = 1_048_576  # 1 MB


def load_spec(source: str | Path | dict[str, Any]) -> AgentSpec:
    """Load and validate an AgentSpec from a file path or a pre-parsed dict.

    Pre:
        If source is a str/Path, the file must exist and be ≤ 1 MB in size
        (checked in bytes BEFORE reading content — borda check per ADR-0008, AC12).
        If source is a dict, it must represent a valid AgentSpec payload.

    Post:
        Returns a fully-validated, immutable AgentSpec instance.

    Invariant:
        Round-trip stability: load_spec(agent.model_dump_json()) produces an
        equivalent AgentSpec (AC7).

    Args:
        source: File path (str or Path) pointing to a UTF-8 JSON file, or a
                pre-parsed dict. String paths are converted to Path internally.

    Returns:
        Validated AgentSpec instance.

    Raises:
        TranspilerError: with code='E_TRANSPILER_SCHEMA' when:
            - The file exceeds 1 MB (checked before reading).
            - The JSON does not conform to AgentSpec (Pydantic validation failure).
            Only the FIRST validation error is reported. This is a deliberate
            choice for clarity: one actionable error at a time is easier to fix
            than a wall of messages. Subsequent errors appear after the first
            is corrected.

    Note:
        Pydantic ValidationError is always translated to TranspilerError — callers
        of this function must never catch pydantic.ValidationError directly.
    """
    data: dict[str, Any]

    if isinstance(source, (str, Path)):
        path = Path(source)
        file_size = path.stat().st_size
        if file_size > _MAX_SPEC_BYTES:
            raise TranspilerError(
                code="E_TRANSPILER_SCHEMA",
                message=(
                    f"spec.json excede 1 MB (observado: {file_size:,} bytes). "
                    f"Reduza o arquivo antes de passar ao transpilador."
                ),
                hint=(
                    "O cap de 1 MB está definido em ADR-0008. "
                    "Mova strings longas para fora do spec.json."
                ),
                path=str(path),
                context={"file_size_bytes": file_size, "cap_bytes": _MAX_SPEC_BYTES},
            )
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = source

    try:
        return AgentSpec.model_validate(data)
    except pydantic.ValidationError as exc:
        first_error = exc.errors(include_url=False)[0]
        loc = first_error.get("loc", ())
        pydantic_msg = first_error.get("msg", str(exc))
        pydantic_type = first_error.get("type", "")
        path_str, context = format_validation_error(exc, loc)

        pydantic_ctx = first_error.get("ctx", {})
        message = _build_user_message(loc, pydantic_msg, pydantic_type, data, pydantic_ctx)
        hint = _build_hint(pydantic_type, loc)

        raise TranspilerError(
            code="E_TRANSPILER_SCHEMA",
            message=message,
            hint=hint,
            path=path_str,
            context=context,
        ) from exc


# ---------------------------------------------------------------------------
# Internal helpers — kept small to respect the 25-line heuristic (GUIDELINES)
# ---------------------------------------------------------------------------


def _build_user_message(
    loc: tuple[int | str, ...],
    pydantic_msg: str,
    pydantic_type: str,
    data: dict[str, Any],
    pydantic_ctx: dict[str, Any] | None = None,
) -> str:
    """Compose a PT-BR user-facing message from a Pydantic error entry.

    Args:
        loc: Field location tuple from Pydantic.
        pydantic_msg: Raw message from Pydantic.
        pydantic_type: Pydantic error type string (e.g. 'literal_error').
        data: The original input dict (used for received-value context).
        pydantic_ctx: The 'ctx' dict from the Pydantic error entry, carrying
                      limit values (e.g. max_length).

    Returns:
        A PT-BR string describing the error with field path.
    """
    ctx = pydantic_ctx or {}
    path_str = ".".join(str(p) for p in loc) if loc else "(raiz)"

    if pydantic_type == "literal_error" and loc and loc[-1] == "model":
        allowed = ["gemini-2.5-flash"]
        received = data.get("model", "<ausente>")
        return (
            f"Campo `model` inválido: '{received}' não é um valor aceito. "
            f"Valores permitidos: {allowed}."
        )

    if pydantic_type == "string_pattern_mismatch":
        return (
            f"Campo `{path_str}` não corresponde ao padrão permitido. "
            f"Use apenas letras minúsculas, dígitos e hífens (regex: ^[a-z0-9][a-z0-9-]*$)."
        )

    if pydantic_type == "extra_forbidden":
        # loc[-1] is the unknown field name
        field = loc[-1] if loc else "desconhecido"
        return (
            f"Campo desconhecido `{field}` não é permitido pelo schema. "
            f"O schema é fechado (ADR-0006); remova o campo do spec.json."
        )

    if pydantic_type in ("too_long", "string_too_long"):
        _list_fields = {"mcp_servers", "http_tools", "tool_filter"}
        last_loc = loc[-1] if loc else None
        limit = ctx.get("max_length", "")
        if last_loc in _list_fields:
            return (
                f"A lista '{last_loc}' excede o tamanho máximo permitido ({limit} itens). "
                f"Reduza o número de itens."
            )
        return (
            f"O campo '{path_str}' excede o tamanho máximo permitido ({limit} caracteres). "
            f"Reduza o valor."
        )

    if pydantic_type in ("url_parsing", "url_scheme"):
        return (
            f"Campo `{path_str}` contém uma URL inválida. "
            f"Use o formato http://host:porta/caminho."
        )

    if pydantic_type == "missing":
        return (
            f"Campo obrigatório `{path_str}` está ausente. "
            f"Adicione o campo ao spec.json."
        )

    # Generic fallback
    return f"Campo `{path_str}` inválido: {pydantic_msg}."


def _build_hint(pydantic_type: str, loc: tuple[int | str, ...]) -> str:
    """Return a corrective-action hint in PT-BR for a given Pydantic error type.

    Args:
        pydantic_type: Pydantic error type string.
        loc: Field location tuple.

    Returns:
        A hint string in PT-BR. Returns a generic hint when type is unrecognised.
    """
    if pydantic_type == "literal_error" and loc and loc[-1] == "model":
        return (
            "Defina `model` como 'gemini-2.5-flash'. "
            "Outros modelos exigem nova ADR (ADR-0006)."
        )

    if pydantic_type == "string_pattern_mismatch":
        return (
            "Renomeie o campo para usar apenas letras minúsculas, dígitos e hífens. "
            "Exemplo válido: 'medical-order-agent'."
        )

    if pydantic_type == "extra_forbidden":
        return (
            "Consulte docs/ARCHITECTURE.md § 'Schema Pydantic do JSON spec' "
            "para a lista de campos permitidos."
        )

    if pydantic_type in ("url_parsing", "url_scheme"):
        return "Exemplo de URL válida: http://ocr-mcp:8001/sse"

    return "Verifique o arquivo spec.json contra o schema em docs/ARCHITECTURE.md § Schema Pydantic."
