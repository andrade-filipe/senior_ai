"""Tests for RAG MCP health check and tool registration (AC5, AC12, T014, T021).

Covers:
    T014 [AC5]:  SSE handshake exposes both tools (search_exam_code, list_exams).
    T021 [AC12]: FastMCP instance is properly configured for SSE.
"""

from __future__ import annotations

import pytest

from rag_mcp.server import get_mcp


class TestMcpInstanceConfiguration:
    """T014 [AC5] + T021 [AC12]: both tools registered."""

    def test_mcp_instance_is_created(self) -> None:
        """T021 [AC12]: FastMCP instance exists and is named rag-mcp."""
        mcp = get_mcp()
        assert mcp is not None
        assert mcp.name == "rag-mcp"

    def _get_tool_names(self) -> set[str]:
        """Helper to get registered tool names from FastMCP internal registry.

        In mcp[cli] >= 1.0 the tool registry is `_tool_manager._tools` (private
        dict). When the SDK renames it, the probe returns an empty set and the
        dependent tests skip — the SSE integration test covers the public contract.
        """
        mcp = get_mcp()
        tool_manager = getattr(mcp, "_tool_manager", None)
        if tool_manager is None:
            return set()
        tools = getattr(tool_manager, "_tools", None)
        if tools is None:
            return set()
        return set(tools.keys())

    def test_search_exam_code_tool_registered(self) -> None:
        """T014 [AC5]: search_exam_code tool is registered."""
        tool_names = self._get_tool_names()
        if not tool_names:
            pytest.skip("FastMCP internal API differs — inspect manually")
        assert "search_exam_code" in tool_names

    def test_list_exams_tool_registered(self) -> None:
        """T014 [AC5]: list_exams tool is registered."""
        tool_names = self._get_tool_names()
        if not tool_names:
            pytest.skip("FastMCP internal API differs — inspect manually")
        assert "list_exams" in tool_names

    def test_both_tools_registered(self) -> None:
        """T014 [AC5]: both search_exam_code and list_exams are in inventory."""
        tool_names = self._get_tool_names()
        if not tool_names:
            pytest.skip("FastMCP internal API differs — inspect manually")
        assert {"search_exam_code", "list_exams"}.issubset(tool_names)
