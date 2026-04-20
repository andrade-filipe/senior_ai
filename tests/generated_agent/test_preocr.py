"""RED tests — spec 0010 T010/T011/T013 [DbC].

Targets for the pre-OCR CLI module (generated_agent/preocr.py) — does not
exist yet; these tests must fail until Onda C (GREEN) lands the
implementation.

Covers:
  - T010 / AC1: _run_preocr calls MCP session.call_tool with the right args
    and returns list[str].
  - T011 / AC3: _build_preocr_prompt returns a single text Part with the
    canonical prefix and no inline_data anywhere.
  - T013 / AC6: _run_preocr raises _PreOcrError(code="E_MCP_UNAVAILABLE")
    when the MCP call exceeds PREOCR_MCP_TIMEOUT_SECONDS.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


_SAMPLE_URL = "http://ocr-mcp:8001/sse"
_SAMPLE_CID = "cid-0010-preocr"


class _FakeCallToolResult:
    """Stand-in for mcp.types.CallToolResult."""

    def __init__(self, structured_content: Any = None, content: Any = None) -> None:
        # The real CallToolResult exposes structured output (list, dict, str)
        # via .structuredContent / .structured_content; tolerate both.
        self.structuredContent = structured_content
        self.structured_content = structured_content
        self.content = content if content is not None else []
        self.isError = False


def _make_fake_session(call_tool_return: Any) -> tuple[MagicMock, list[tuple[str, dict[str, Any]]]]:
    """Build a MagicMock ClientSession and capture call_tool invocations."""
    captured: list[tuple[str, dict[str, Any]]] = []
    session = MagicMock()
    session.initialize = AsyncMock(return_value=None)

    async def _fake_call_tool(name: str, arguments: dict[str, Any] | None = None, **_: Any) -> Any:
        captured.append((name, arguments or {}))
        return call_tool_return

    session.call_tool = AsyncMock(side_effect=_fake_call_tool)
    return session, captured


@asynccontextmanager
async def _fake_sse_client(*_args: Any, **_kwargs: Any):
    """Async contextmanager yielding (read_stream, write_stream) stubs."""
    yield (MagicMock(), MagicMock())


@asynccontextmanager
async def _fake_client_session(*_args: Any, **_kwargs: Any):
    yield MagicMock()


def test_calls_mcp_and_returns_exams() -> None:
    """T010 [DbC] / AC1 — _run_preocr forwards bytes to extract_exams_from_image.

    Pre: image_bytes non-empty, mcp_url valid SSE URL.
    Post: returns list[str]; session.call_tool invoked once with
          ("extract_exams_from_image", {"image_base64": <b64>}).
    """
    from generated_agent.preocr import _run_preocr  # noqa: PLC0415 — RED import

    exams_return = _FakeCallToolResult(
        structured_content={"result": ["Hemograma Completo", "Glicemia de Jejum"]},
    )
    session, captured = _make_fake_session(exams_return)

    async def _call() -> list[str]:
        with (
            patch("generated_agent.preocr.sse_client", _fake_sse_client),
            patch(
                "generated_agent.preocr.ClientSession",
                lambda *_a, **_k: _ctx_returning(session),
            ),
        ):
            return await _run_preocr(
                image_bytes=b"\x89PNG\r\n\x1a\nFAKE",
                correlation_id=_SAMPLE_CID,
                mcp_url=_SAMPLE_URL,
                timeout_s=5.0,
                connect_retries=0,
            )

    result = asyncio.run(_call())

    assert isinstance(result, list)
    assert all(isinstance(x, str) for x in result)
    assert result == ["Hemograma Completo", "Glicemia de Jejum"]

    assert len(captured) == 1, f"expected exactly one call_tool invocation, got {captured}"
    tool_name, args = captured[0]
    assert tool_name == "extract_exams_from_image"
    assert set(args.keys()) == {"image_base64"}
    # base64 of b"\x89PNG\r\n\x1a\nFAKE"
    import base64

    assert args["image_base64"] == base64.b64encode(b"\x89PNG\r\n\x1a\nFAKE").decode("ascii")


def _ctx_returning(value: Any):
    @asynccontextmanager
    async def _ctx() -> Any:
        yield value

    return _ctx()


def test_build_prompt_contains_exam_list_and_no_inline_data() -> None:
    """T011 [DbC] / AC3 — prompt is a single text Part, no inline_data, canonical prefix.

    Pre: exams: list[str].
    Post: Content(role="user", parts=[Part(text=...)]) with exactly one Part,
          text carrying "EXAMES DETECTADOS (OCR pré-executado pelo CLI):" and
          the serialized exam list; no Part anywhere has inline_data.
    """
    from generated_agent.preocr import _build_preocr_prompt  # noqa: PLC0415 — RED import

    exams = ["Hemograma Completo", "Glicemia de Jejum"]
    content = _build_preocr_prompt(exams)

    # Exactly one Part.
    parts = getattr(content, "parts", None)
    assert parts is not None, "Content must expose .parts"
    assert len(parts) == 1, f"expected single Part, got {len(parts)}"

    # Part is textual — no inline_data on any part.
    for p in parts:
        inline = getattr(p, "inline_data", None)
        assert inline is None, f"Part must not carry inline_data, got {inline!r}"
        part_text = getattr(p, "text", None)
        assert isinstance(part_text, str) and part_text, "Part.text must be a non-empty str"

    text = parts[0].text
    assert "EXAMES DETECTADOS (OCR pré-executado pelo CLI):" in text, (
        f"canonical prefix missing from prompt: {text!r}"
    )
    # Exam names appear (JSON array, any order).
    for name in exams:
        assert name in text, f"exam {name!r} missing from prompt text"

    # Role must be user.
    assert getattr(content, "role", None) == "user"


def test_timeout_raises_preocr_error() -> None:
    """T013 [DbC] / AC6 — timeout maps to _PreOcrError(code=E_MCP_UNAVAILABLE).

    Pre: session.call_tool hangs beyond timeout_s.
    Post: _PreOcrError raised with code="E_MCP_UNAVAILABLE"; no silent fallback.
    """
    from generated_agent.preocr import _PreOcrError, _run_preocr  # noqa: PLC0415 — RED import

    async def _hang(*_a: Any, **_k: Any) -> Any:
        await asyncio.sleep(10)  # way beyond timeout_s below
        return _FakeCallToolResult(structured_content={"result": []})

    session = MagicMock()
    session.initialize = AsyncMock(return_value=None)
    session.call_tool = AsyncMock(side_effect=_hang)

    async def _call() -> None:
        with (
            patch("generated_agent.preocr.sse_client", _fake_sse_client),
            patch(
                "generated_agent.preocr.ClientSession",
                lambda *_a, **_k: _ctx_returning(session),
            ),
        ):
            await _run_preocr(
                image_bytes=b"\x89PNG",
                correlation_id=_SAMPLE_CID,
                mcp_url=_SAMPLE_URL,
                timeout_s=0.1,
                connect_retries=0,
            )

    with pytest.raises(_PreOcrError) as exc_info:
        asyncio.run(_call())

    assert exc_info.value.code == "E_MCP_UNAVAILABLE", (
        f"expected code E_MCP_UNAVAILABLE, got {exc_info.value.code!r}"
    )


# ---------------------------------------------------------------------------
# Camada D — CLI pre-filter (spec 0009 T080–T082)
# ---------------------------------------------------------------------------


class TestPrefilterExams:
    """Spec 0009 Camada D — drop PII placeholders + strip bullet prefixes.

    Evidence (2026-04-20 E2E with gemini-2.5-pro): OCR returned
    ["Hemograma Completo", "Glicemia de Jejum", "<LOCATION>", "1. Colesterol"]
    — the <LOCATION> placeholder was sent to the LLM as a real exam and the
    numeric bullet leaked into the RAG query. Pre-filter runs in the CLI
    before _build_preocr_prompt.
    """

    def test_prefilter_drops_pii_placeholders(self) -> None:
        from generated_agent.preocr import _prefilter_exams  # noqa: PLC0415

        result = _prefilter_exams(
            ["Hemograma", "<LOCATION>", "<PERSON>", "<CPF>", "Glicemia"]
        )
        assert result == ["Hemograma", "Glicemia"]

    def test_prefilter_strips_numeric_bullets(self) -> None:
        from generated_agent.preocr import _prefilter_exams  # noqa: PLC0415

        result = _prefilter_exams(
            ["1. Hemograma Completo", "2) Glicemia de Jejum", "a) Colesterol Total"]
        )
        assert result == ["Hemograma Completo", "Glicemia de Jejum", "Colesterol Total"]

    def test_prefilter_preserves_clean_names(self) -> None:
        from generated_agent.preocr import _prefilter_exams  # noqa: PLC0415

        clean = ["Hemograma Completo", "Glicemia de Jejum", "TSH"]
        assert _prefilter_exams(clean) == clean

    def test_prefilter_drops_empty_after_strip(self) -> None:
        from generated_agent.preocr import _prefilter_exams  # noqa: PLC0415

        result = _prefilter_exams(["   ", "1. ", "Hemograma"])
        assert result == ["Hemograma"]
