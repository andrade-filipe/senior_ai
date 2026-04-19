"""E2E flow tests — all skipped until docker compose is up (Block 0008).

These tests require the full stack:
  - ocr-mcp on :8001
  - rag-mcp on :8002
  - scheduling-api on :8000
  - generated_agent with valid GOOGLE_API_KEY
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="requires docker compose — Bloco 0008")
def test_flow_within_5_tool_calls() -> None:
    """AC1 / T010: entire flow completes in <= 5 tool calls.

    Verify by parsing logs for event=tool.called entries.
    """
    raise NotImplementedError


@pytest.mark.skip(reason="requires docker compose — Bloco 0008")
def test_rag_calls_in_parallel() -> None:
    """AC2 / T011: N search_exam_code calls happen within a < 100ms window."""
    raise NotImplementedError


@pytest.mark.skip(reason="requires docker compose — Bloco 0008")
def test_single_post_appointments() -> None:
    """AC3 / T012: exactly one POST /api/v1/appointments regardless of exam count."""
    raise NotImplementedError


@pytest.mark.skip(reason="requires docker compose — Bloco 0008")
def test_post_body_patient_ref_pattern() -> None:
    """AC5 / T014: POST body patient_ref matches ^anon-[a-z0-9]+$."""
    raise NotImplementedError


@pytest.mark.skip(reason="requires docker compose — Bloco 0008")
def test_rag_null_triggers_list_exams_degraded_mode() -> None:
    """AC8 / T017: when search_exam_code returns None, agent calls list_exams(limit=5)."""
    raise NotImplementedError


@pytest.mark.skip(reason="requires docker compose — Bloco 0008")
def test_final_output_has_source_score_correlation_id() -> None:
    """AC9 / T018: final output cites (rag-mcp, score=<float>, correlation_id=<id>)."""
    raise NotImplementedError


@pytest.mark.skip(reason="requires docker compose — Bloco 0008")
def test_low_score_marked_inconclusive() -> None:
    """AC10 / T019: match with score < 0.80 is labeled 'nao-conclusivo'."""
    raise NotImplementedError


@pytest.mark.skip(reason="requires docker compose — Bloco 0008")
def test_rag_none_triggers_list_exams_limit_20() -> None:
    """AC14 / T023 [DbC]: E_RAG_NO_MATCH -> zero retry, calls list_exams(limit=20)."""
    raise NotImplementedError
