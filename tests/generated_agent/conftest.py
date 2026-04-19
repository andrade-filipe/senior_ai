"""Shared fixtures for generated_agent tests.

Integration fixtures (compose_up_subset) are only usable when
docker compose is running — see @pytest.mark.skip decorators on
integration tests (Block 0008 wave).
"""

from __future__ import annotations

import pytest


@pytest.fixture()
def sample_medical_order_png() -> str:
    """Return absolute path to the canonical fixture PNG.

    The PNG must exist at docs/fixtures/sample_medical_order.png.
    """
    from pathlib import Path

    path = Path(__file__).parent.parent.parent / "docs" / "fixtures" / "sample_medical_order.png"
    assert path.exists(), f"Fixture PNG missing: {path}"
    return str(path)


@pytest.fixture()
def spec_example_path() -> str:
    """Return absolute path to docs/fixtures/spec.example.json."""
    from pathlib import Path

    path = Path(__file__).parent.parent.parent / "docs" / "fixtures" / "spec.example.json"
    assert path.exists(), f"spec.example.json missing: {path}"
    return str(path)
