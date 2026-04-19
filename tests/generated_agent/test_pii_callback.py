"""Test AC4 / T013: before_model_callback strips PII from LLM requests.

Green in this wave (unit — no Docker, no real LLM required).
Tests both the make_pii_callback factory (security module) and that
generated agent.py registers it on root_agent.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch


class _FakePart:
    """Minimal stand-in for google.genai.types.Part."""

    def __init__(self, text: str) -> None:
        self.text = text


class _FakeContent:
    """Minimal stand-in for google.genai.types.Content."""

    def __init__(self, parts: list[_FakePart]) -> None:
        self.parts = parts


class _FakeLlmRequest:
    """Minimal stand-in for ADK LlmRequest."""

    def __init__(self, texts: list[str]) -> None:
        self.contents = [_FakeContent([_FakePart(t) for t in texts])]


def test_make_pii_callback_factory_exists() -> None:
    """security.make_pii_callback must be importable."""
    from security import make_pii_callback

    cb = make_pii_callback(allow_list=[])
    assert callable(cb)


def test_before_model_callback_strips_pii() -> None:
    """AC4 / T013 [DbC]: callback masks PII in llm_request text parts in-place.

    Invariant:
        After callback runs, no raw CPF or PERSON value remains in parts[*].text.
    """
    from security import make_pii_callback

    pii_text = "Joao Silva CPF 111.444.777-35 quer agendar exame"
    request = _FakeLlmRequest([pii_text])
    cb = make_pii_callback(allow_list=[])
    cb(None, request)  # callback_context, llm_request

    masked = request.contents[0].parts[0].text
    # Raw CPF digits pattern must be gone
    import re

    assert not re.search(r"\d{3}\.\d{3}\.\d{3}-\d{2}", masked), (
        f"CPF still present in masked text: {masked!r}"
    )


def test_callback_leaves_non_pii_intact() -> None:
    """Non-PII text must not be altered by the callback."""
    from security import make_pii_callback

    clean_text = "Hemograma Completo e Glicemia de Jejum"
    request = _FakeLlmRequest([clean_text])
    cb = make_pii_callback(allow_list=[])
    cb(None, request)

    assert request.contents[0].parts[0].text == clean_text


def test_callback_handles_no_contents_gracefully() -> None:
    """Callback must not crash when llm_request has no contents attribute."""
    from security import make_pii_callback

    cb = make_pii_callback(allow_list=[])
    # Object with no 'contents'
    cb(None, object())  # must not raise


def test_build_agent_mcp_headers_include_correlation_id() -> None:
    """BLOCKER-2: _build_agent injects X-Correlation-ID into McpToolset SSE headers.

    Stubs McpToolset and asserts the headers dict passed includes
    'X-Correlation-ID' with the expected value.
    """
    import sys
    from types import ModuleType
    from unittest.mock import MagicMock

    # Build minimal fake ADK hierarchy
    fake_adk = ModuleType("google")
    fake_adk_adk = ModuleType("google.adk")
    fake_adk_agents = ModuleType("google.adk.agents")
    fake_adk_tools = ModuleType("google.adk.tools")
    fake_adk_mcp = ModuleType("google.adk.tools.mcp_tool")
    fake_adk_mcp_mgr = ModuleType("google.adk.tools.mcp_tool.mcp_session_manager")
    fake_adk_openapi = ModuleType("google.adk.tools.openapi_tool")
    fake_adk_openapi_parser = ModuleType("google.adk.tools.openapi_tool.openapi_spec_parser")
    fake_adk_openapi_toolset = ModuleType(
        "google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset"
    )
    fake_adk_base_tool = ModuleType("google.adk.tools.base_tool")
    fake_adk_base_toolset = ModuleType("google.adk.tools.base_toolset")

    captured_headers: list[dict] = []

    class FakeLlmAgent:
        def __init__(self, **kwargs: Any) -> None:
            self.tools = kwargs.get("tools", [])
            self.before_model_callback = kwargs.get("before_model_callback")

    class FakeMcpToolset:
        def __init__(self, **kwargs: Any) -> None:
            params = kwargs.get("connection_params")
            if params is not None:
                captured_headers.append(params.headers)

    class FakeStreamableHTTPConnectionParams:
        def __init__(self, **kwargs: Any) -> None:
            self.url = kwargs.get("url", "")
            self.headers = kwargs.get("headers", {})

    class FakeOpenAPIToolset:
        def __init__(self, **kwargs: Any) -> None:
            pass

    fake_adk_agents.LlmAgent = FakeLlmAgent
    fake_adk_mcp.McpToolset = FakeMcpToolset
    fake_adk_mcp_mgr.StreamableHTTPConnectionParams = FakeStreamableHTTPConnectionParams
    fake_adk_openapi_toolset.OpenAPIToolset = FakeOpenAPIToolset
    fake_adk_base_tool.BaseTool = object
    fake_adk_base_toolset.BaseToolset = object

    mods_to_patch = {
        "google": fake_adk,
        "google.adk": fake_adk_adk,
        "google.adk.agents": fake_adk_agents,
        "google.adk.tools": fake_adk_tools,
        "google.adk.tools.base_tool": fake_adk_base_tool,
        "google.adk.tools.base_toolset": fake_adk_base_toolset,
        "google.adk.tools.mcp_tool": fake_adk_mcp,
        "google.adk.tools.mcp_tool.mcp_session_manager": fake_adk_mcp_mgr,
        "google.adk.tools.openapi_tool": fake_adk_openapi,
        "google.adk.tools.openapi_tool.openapi_spec_parser": fake_adk_openapi_parser,
        "google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset": fake_adk_openapi_toolset,
    }

    # Remove cached module to force fresh import
    for mod in list(sys.modules.keys()):
        if "generated_agent.agent" in mod:
            del sys.modules[mod]

    test_cid = "test-correlation-id-12345"

    with patch.dict(sys.modules, mods_to_patch):
        import importlib

        agent_mod = importlib.import_module("generated_agent.agent")
        # Reset module-level boot agent so we test factory directly
        for mod in list(sys.modules.keys()):
            if "generated_agent.agent" in mod:
                del sys.modules[mod]
        agent_mod2 = importlib.import_module("generated_agent.agent")

    # Reload fresh without cached boot agent to call _build_agent directly
    for mod in list(sys.modules.keys()):
        if "generated_agent.agent" in mod:
            del sys.modules[mod]

    with patch.dict(sys.modules, mods_to_patch):
        import importlib

        captured_headers.clear()
        agent_mod3 = importlib.import_module("generated_agent.agent")
        # Module-level import calls _build_agent("boot") — check headers had "boot"
        # Then call with specific cid
        captured_headers.clear()
        agent_mod3._build_agent(test_cid)

    assert len(captured_headers) >= 1, "No McpToolset headers captured"
    for headers in captured_headers:
        assert "X-Correlation-ID" in headers, (
            f"X-Correlation-ID missing from McpToolset headers: {headers}"
        )
        assert headers["X-Correlation-ID"] == test_cid


def test_callback_registered_on_root_agent() -> None:
    """AC4 [DbC]: root_agent must have before_model_callback registered (ADR-0003).

    This test patches heavy ADK imports so it runs without installed google-adk.
    """
    import sys
    from types import ModuleType

    # Build a minimal fake ADK hierarchy so generated_agent.agent can be imported
    fake_adk = ModuleType("google")
    fake_adk_adk = ModuleType("google.adk")
    fake_adk_agents = ModuleType("google.adk.agents")
    fake_adk_tools = ModuleType("google.adk.tools")
    fake_adk_mcp = ModuleType("google.adk.tools.mcp_tool")
    fake_adk_mcp_mgr = ModuleType("google.adk.tools.mcp_tool.mcp_session_manager")
    fake_adk_openapi = ModuleType("google.adk.tools.openapi_tool")
    fake_adk_openapi_parser = ModuleType("google.adk.tools.openapi_tool.openapi_spec_parser")
    fake_adk_openapi_toolset = ModuleType(
        "google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset"
    )

    recorded: dict[str, Any] = {}

    class FakeLlmAgent:
        def __init__(self, **kwargs: Any) -> None:
            recorded.update(kwargs)

    class FakeMcpToolset:
        def __init__(self, **kwargs: Any) -> None:
            pass

    class FakeStreamableHTTPConnectionParams:
        def __init__(self, **kwargs: Any) -> None:
            pass

    class FakeOpenAPIToolset:
        def __init__(self, **kwargs: Any) -> None:
            pass

    fake_adk_agents.LlmAgent = FakeLlmAgent
    fake_adk_mcp.McpToolset = FakeMcpToolset
    fake_adk_mcp_mgr.StreamableHTTPConnectionParams = FakeStreamableHTTPConnectionParams
    fake_adk_openapi_toolset.OpenAPIToolset = FakeOpenAPIToolset

    mods_to_patch = {
        "google": fake_adk,
        "google.adk": fake_adk_adk,
        "google.adk.agents": fake_adk_agents,
        "google.adk.tools": fake_adk_tools,
        "google.adk.tools.mcp_tool": fake_adk_mcp,
        "google.adk.tools.mcp_tool.mcp_session_manager": fake_adk_mcp_mgr,
        "google.adk.tools.openapi_tool": fake_adk_openapi,
        "google.adk.tools.openapi_tool.openapi_spec_parser": fake_adk_openapi_parser,
        "google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset": fake_adk_openapi_toolset,
    }

    # Remove previously cached module to force fresh import
    for mod in list(sys.modules.keys()):
        if "generated_agent.agent" in mod:
            del sys.modules[mod]

    with patch.dict(sys.modules, mods_to_patch):
        import importlib

        agent_mod = importlib.import_module("generated_agent.agent")
        # root_agent is lazy (MAJOR-5 round-2); access triggers _build_agent("boot")
        _ = agent_mod.root_agent

    cb = recorded.get("before_model_callback")
    assert cb is not None, "before_model_callback not registered on root_agent (ADR-0003)"
    assert callable(cb)
