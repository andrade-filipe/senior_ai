"""Tests for transpiler.schema — AgentSpec validation (RED phase).

Each test maps to one Acceptance Criterion from
docs/specs/0001-agentspec-schema/spec.md. Tests tagged [DbC] exercise
formal Design-by-Contract invariants documented in plan.md § Design by Contract.

Run:
    uv run pytest transpiler/tests/test_schema.py -v
"""

import json
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from transpiler import AgentSpec, TranspilerError, load_spec


# ---------------------------------------------------------------------------
# AC1 — [DbC AgentSpec.Invariant]
# A well-formed spec matching spec.example.json must parse without errors.
# ---------------------------------------------------------------------------


def test_valid_example_parses(spec_example_dict: dict[str, Any]) -> None:
    """AC1 — canonical example spec parses into a valid AgentSpec instance.

    DbC: AgentSpec.Invariant — model is in allowlist, name matches regex,
    at least one of mcp_servers / http_tools is non-empty.
    """
    agent = load_spec(spec_example_dict)

    assert isinstance(agent, AgentSpec)
    assert agent.name == "medical-order-agent"
    assert agent.model == "gemini-2.5-flash"
    assert len(agent.mcp_servers) == 2
    assert len(agent.http_tools) == 1


# ---------------------------------------------------------------------------
# AC2 — model allowlist: retrocompat + new lite value + rejection with message
# ---------------------------------------------------------------------------


def test_model_gemini_flash_accepted(spec_example_dict: dict[str, Any]) -> None:
    """AC2 / ADR-0009 — 'gemini-2.5-flash' remains a valid model (retrocompat).

    Widening the Literal must not break specs already using the original model.
    """
    spec = deepcopy(spec_example_dict)
    spec["model"] = "gemini-2.5-flash"
    agent = load_spec(spec)
    assert agent.model == "gemini-2.5-flash"


def test_model_gemini_flash_lite_accepted(spec_example_dict: dict[str, Any]) -> None:
    """AC2 / ADR-0009 — 'gemini-2.5-flash-lite' is accepted after Literal widening."""
    spec = deepcopy(spec_example_dict)
    spec["model"] = "gemini-2.5-flash-lite"
    agent = load_spec(spec)
    assert agent.model == "gemini-2.5-flash-lite"


def test_invalid_model_rejected(spec_example_dict: dict[str, Any]) -> None:
    """AC2 — model value outside Literal allowlist raises TranspilerError E_TRANSPILER_SCHEMA.

    The error message must list BOTH accepted values so the operator knows their
    options after ADR-0009 widened the allowlist.
    """
    bad = deepcopy(spec_example_dict)
    bad["model"] = "gpt-4"

    with pytest.raises(TranspilerError) as exc_info:
        load_spec(bad)

    err = exc_info.value
    assert err.code == "E_TRANSPILER_SCHEMA"
    # message must mention the offending field and BOTH accepted values
    combined = f"{err.message} {err.hint or ''}"
    assert "model" in combined.lower()
    assert "gemini-2.5-flash" in combined
    assert "gemini-2.5-flash-lite" in combined


# ---------------------------------------------------------------------------
# AC3 — name does not match ^[a-z0-9][a-z0-9-]*$
# ---------------------------------------------------------------------------


def test_name_pattern_rejected(spec_example_dict: dict[str, Any]) -> None:
    """AC3 — name with space/uppercase raises TranspilerError citing regex."""
    bad = deepcopy(spec_example_dict)
    bad["name"] = "Invalid Name"

    with pytest.raises(TranspilerError) as exc_info:
        load_spec(bad)

    err = exc_info.value
    assert err.code == "E_TRANSPILER_SCHEMA"
    combined = f"{err.message} {err.hint or ''}"
    assert "name" in combined.lower()
    assert "a-z0-9" in combined


# ---------------------------------------------------------------------------
# AC4 — extra field outside frozen schema — [DbC AgentSpec.Invariant]
# ---------------------------------------------------------------------------


def test_extra_field_rejected(spec_example_dict: dict[str, Any]) -> None:
    """AC4 — unknown field memory_type raises TranspilerError (extra='forbid').

    DbC: AgentSpec.Invariant — schema is closed; no unknown keys allowed.
    """
    bad = deepcopy(spec_example_dict)
    bad["memory_type"] = "vector"

    with pytest.raises(TranspilerError) as exc_info:
        load_spec(bad)

    err = exc_info.value
    assert err.code == "E_TRANSPILER_SCHEMA"
    assert "memory_type" in f"{err.message} {err.hint or ''}"


# ---------------------------------------------------------------------------
# AC5 — both mcp_servers and http_tools absent/empty
# ---------------------------------------------------------------------------


def test_missing_required_field_rejected() -> None:
    """AC5 — spec without both mcp_servers and http_tools raises TranspilerError.

    Both fields have default_factory=list so Pydantic accepts their absence;
    the model_validator enforces the at-least-one invariant (AC5).
    """
    # Omitting both list fields: they default to [] and model_validator fires
    minimal: dict[str, Any] = {
        "name": "test-agent",
        "description": "test",
        "model": "gemini-2.5-flash",
        "instruction": "do stuff",
    }

    with pytest.raises(TranspilerError) as exc_info:
        load_spec(minimal)

    err = exc_info.value
    assert err.code == "E_TRANSPILER_SCHEMA"


# ---------------------------------------------------------------------------
# AC6 — invalid URL in mcp_servers — [DbC McpServerSpec.Post]
# ---------------------------------------------------------------------------


def test_invalid_url_rejected(spec_example_dict: dict[str, Any]) -> None:
    """AC6 — malformed URL in mcp_servers[0].url raises TranspilerError.

    DbC: McpServerSpec.Post — url must be validated as AnyHttpUrl.
    Error must cite the field path including 'url'.
    Message must explicitly mention URL in PT-BR text or hint.
    """
    bad = deepcopy(spec_example_dict)
    bad["mcp_servers"] = [{"name": "ocr", "url": "not-a-url"}]

    with pytest.raises(TranspilerError) as exc_info:
        load_spec(bad)

    err = exc_info.value
    assert err.code == "E_TRANSPILER_SCHEMA"
    # path or message must reference the url field
    combined = f"{err.message} {err.path or ''} {err.hint or ''}"
    assert "url" in combined.lower()
    # PT-BR message or hint must explicitly cite URL (not just error code)
    assert "URL" in err.message.upper() or "url" in (err.hint or "").lower()


# ---------------------------------------------------------------------------
# AC7 — round-trip JSON stability — [DbC load_spec.Invariant]
# ---------------------------------------------------------------------------


def test_roundtrip_json(spec_example_dict: dict[str, Any]) -> None:
    """AC7 — model_dump_json() → load_spec() produces an equivalent instance.

    DbC: load_spec.Invariant — round-trip is stable (idempotent).
    """
    agent1 = load_spec(spec_example_dict)
    serialized = agent1.model_dump_json()
    agent2 = load_spec(json.loads(serialized))

    assert agent1.model_dump() == agent2.model_dump()


# ---------------------------------------------------------------------------
# AC9 — duplicate mcp_server names — [DbC McpServerSpec.Invariant]
# ---------------------------------------------------------------------------


def test_duplicate_mcp_server_names_rejected(spec_example_dict: dict[str, Any]) -> None:
    """AC9 — two McpServerSpec entries with identical name raise TranspilerError.

    DbC: McpServerSpec.Invariant — name is unique among siblings in the same AgentSpec.
    """
    bad = deepcopy(spec_example_dict)
    bad["mcp_servers"] = [
        {"name": "x", "url": "http://host-a:8001/sse"},
        {"name": "x", "url": "http://host-b:8002/sse"},
    ]

    with pytest.raises(TranspilerError) as exc_info:
        load_spec(bad)

    err = exc_info.value
    assert err.code == "E_TRANSPILER_SCHEMA"
    combined = f"{err.message} {err.hint or ''}"
    assert "name" in combined.lower()


# ---------------------------------------------------------------------------
# AC10 — list caps enforced (ADR-0008) — [DbC AgentSpec.Invariant]
# ---------------------------------------------------------------------------


def _make_mcp_server(n: int) -> dict[str, Any]:
    return {"name": f"srv-{n}", "url": f"http://host-{n}:8000/sse"}


def _make_http_tool(n: int) -> dict[str, Any]:
    return {"name": f"tool-{n}", "base_url": f"http://api-{n}:8000"}


def test_list_caps_enforced(spec_example_dict: dict[str, Any]) -> None:
    """AC10 — exceeding list caps raises TranspilerError citing E_TRANSPILER_SCHEMA.

    DbC: AgentSpec.Invariant — mcp_servers ≤ 10, http_tools ≤ 20,
    tool_filter ≤ 50 (ADR-0008 guardrails).
    Error message or context must reference the cap value and field name.
    """
    # 11 mcp_servers (cap = 10)
    too_many_mcp = deepcopy(spec_example_dict)
    too_many_mcp["mcp_servers"] = [_make_mcp_server(i) for i in range(11)]
    with pytest.raises(TranspilerError) as exc_info:
        load_spec(too_many_mcp)
    err = exc_info.value
    assert err.code == "E_TRANSPILER_SCHEMA"
    assert "mcp_servers" in err.path or "mcp_servers" in err.message
    assert "10" in err.message or "10" in str(err.context)

    # 21 http_tools (cap = 20)
    too_many_http = deepcopy(spec_example_dict)
    too_many_http["http_tools"] = [_make_http_tool(i) for i in range(21)]
    with pytest.raises(TranspilerError) as exc_info:
        load_spec(too_many_http)
    err = exc_info.value
    assert err.code == "E_TRANSPILER_SCHEMA"
    assert "http_tools" in err.path or "http_tools" in err.message
    assert "20" in err.message or "20" in str(err.context)

    # 51 tool_filter entries in a McpServerSpec (cap = 50)
    too_many_filter = deepcopy(spec_example_dict)
    too_many_filter["mcp_servers"] = [
        {
            "name": "ocr",
            "url": "http://ocr-mcp:8001/sse",
            "tool_filter": [f"tool-{i}" for i in range(51)],
        }
    ]
    with pytest.raises(TranspilerError) as exc_info:
        load_spec(too_many_filter)
    err = exc_info.value
    assert err.code == "E_TRANSPILER_SCHEMA"
    assert "tool_filter" in err.path or "tool_filter" in err.message
    assert "50" in err.message or "50" in str(err.context)


# ---------------------------------------------------------------------------
# AC11 — string caps enforced — [DbC AgentSpec.Invariant + McpServerSpec.Invariant]
# ---------------------------------------------------------------------------


def test_string_caps_enforced(spec_example_dict: dict[str, Any]) -> None:
    """AC11 — strings exceeding caps (or URLs > 2048) raise TranspilerError.

    DbC: AgentSpec.Invariant and McpServerSpec.Invariant:
        - description ≤ 500 chars (ADR-0008)
        - instruction ≤ 4096 bytes UTF-8 (ADR-0008 / AC20, updated from 500)
        - url/base_url/openapi_url ≤ 2048 chars (ADR-0008)
    Error message or context must reference the cap value.
    """
    long_str = "a" * 501

    # description > 500 chars
    bad_description = deepcopy(spec_example_dict)
    bad_description["description"] = long_str
    with pytest.raises(TranspilerError) as exc_info:
        load_spec(bad_description)
    err = exc_info.value
    assert err.code == "E_TRANSPILER_SCHEMA"
    assert "500" in err.message or "500" in str(err.context)

    # instruction > 4096 bytes UTF-8 (ADR-0008 / AC20 — updated cap)
    bad_instruction = deepcopy(spec_example_dict)
    bad_instruction["instruction"] = "a" * 4097  # 4097 ASCII bytes > 4096 cap
    with pytest.raises(TranspilerError) as exc_info:
        load_spec(bad_instruction)
    err = exc_info.value
    assert err.code == "E_TRANSPILER_SCHEMA"
    assert "4096" in err.message or "instruction" in err.message.lower()

    # URL > 2048 chars in mcp_servers[].url
    long_url = "http://host:8001/" + "a" * 2032  # total length > 2048
    bad_url = deepcopy(spec_example_dict)
    bad_url["mcp_servers"] = [{"name": "ocr", "url": long_url}]
    with pytest.raises(TranspilerError) as exc_info:
        load_spec(bad_url)
    err = exc_info.value
    assert err.code == "E_TRANSPILER_SCHEMA"
    assert "2048" in err.message or "url" in err.path.lower()


# ---------------------------------------------------------------------------
# AC12 — file size cap > 1 MB before json.loads — [DbC load_spec.Pre]
# ---------------------------------------------------------------------------


def test_spec_json_size_cap() -> None:
    """AC12 — spec.json > 1 MB raises TranspilerError before json.loads.

    DbC: load_spec.Pre — file size checked in bytes before any read/parse.
    Error message must mention '1 MB'.
    """
    # Construct a JSON file whose byte size exceeds 1 MB
    oversized_content = json.dumps({"pad": "x" * (1024 * 1024)}).encode("utf-8")
    assert len(oversized_content) > 1_048_576, "fixture must be > 1 MB for this test"

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp.write(oversized_content)
        tmp_path = Path(tmp.name)

    try:
        with pytest.raises(TranspilerError) as exc_info:
            load_spec(tmp_path)

        err = exc_info.value
        assert err.code == "E_TRANSPILER_SCHEMA"
        assert "1 MB" in err.message
    finally:
        tmp_path.unlink(missing_ok=True)
