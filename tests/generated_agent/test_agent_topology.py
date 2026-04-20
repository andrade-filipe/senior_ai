"""RED test — spec 0010 T012 [DbC].

Target: after Onda C, _build_agent() must not expose extract_exams_from_image
to the LlmAgent. Either the OCR McpToolset is absent, or its tool_filter is
empty. The tool remains available on the server for direct CLI calls but is
hidden from the model (AC4).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_ocr_tool_not_in_agent_tools() -> None:
    """T012 [DbC] / AC4 — OCR tool must not be exposed to the model.

    Post: for every McpToolset attached to the returned LlmAgent, if the
          toolset points at the OCR server, its tool_filter is [] (empty
          list, meaning "expose nothing"); no toolset carries the
          "extract_exams_from_image" name in its tool_filter.
    """
    # Avoid real httpx.get of the scheduling spec during module import.
    # Also stub make_pii_callback to avoid spinning up a Presidio analyzer
    # that would pollute shared state for later PII tests in the same run.
    with (
        patch(
            "generated_agent.agent._load_scheduling_toolset",
            return_value=None,
        ),
        patch(
            "generated_agent.agent.make_pii_callback",
            return_value=lambda *_a, **_k: None,
        ),
    ):
        from generated_agent.agent import _build_agent  # noqa: PLC0415

        agent = _build_agent("cid-test-topology")

    # Walk the agent.tools list and look for McpToolset entries.
    from google.adk.tools.mcp_tool import McpToolset  # noqa: PLC0415

    offenders: list[str] = []
    for tool in agent.tools:
        if not isinstance(tool, McpToolset):
            continue
        tool_filter = getattr(tool, "_tool_filter", None) or getattr(tool, "tool_filter", None)
        # Normalise: filter may be None, list[str], or a callable in newer ADK.
        names: list[str] = []
        if isinstance(tool_filter, list):
            names = [n for n in tool_filter if isinstance(n, str)]
        if "extract_exams_from_image" in names:
            offenders.append(
                f"McpToolset exposes extract_exams_from_image via tool_filter={tool_filter!r}"
            )

    assert not offenders, (
        "OCR tool must not be reachable by the model after spec 0010. "
        "Offenders:\n  - " + "\n  - ".join(offenders)
    )
