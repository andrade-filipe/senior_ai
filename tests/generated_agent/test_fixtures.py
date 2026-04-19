"""Test AC13 / T022: fixtures exist and spec.example.json is valid.

Green in this wave (unit — no Docker required).
"""

from __future__ import annotations

from pathlib import Path


def test_fixtures_exist_and_spec_valid(spec_example_path: str, sample_medical_order_png: str) -> None:
    """AC13 / T022 [DbC]: both fixture files exist and spec passes load_spec.

    Pre:
        docs/fixtures/spec.example.json and sample_medical_order.png exist.
    Post:
        load_spec returns a valid AgentSpec without raising.
    """
    from transpiler.schema import load_spec

    # PNG exists (asserted by fixture)
    assert Path(sample_medical_order_png).exists()

    # spec.example.json passes the transpiler validator
    spec = load_spec(spec_example_path)
    assert spec.name == "medical-order-agent"
    assert spec.model == "gemini-2.5-flash"
    assert len(spec.mcp_servers) >= 1
    assert len(spec.http_tools) >= 1
    assert spec.guardrails.pii.enabled is True
