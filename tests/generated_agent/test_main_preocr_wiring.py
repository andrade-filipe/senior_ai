"""RED tests — spec 0010 T014 / T015.

Main-level wiring of the pre-OCR step:

- T014 / AC2: when the pre-OCR returns an empty exam list, main() aborts
  with SystemExit(4) and prints the canonical envelope with code
  E_OCR_UNKNOWN_IMAGE on stderr; the LlmAgent runner is never invoked.
- T015 / AC6: when the pre-OCR raises _PreOcrError(E_MCP_UNAVAILABLE),
  main() aborts with SystemExit(5); the LlmAgent runner is never invoked.

Both tests monkey-patch the _run_preocr symbol expected in
generated_agent.__main__ after Onda C. Today this symbol does not exist,
so the tests fail in Onda B — exactly the RED state.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture()
def fake_image(tmp_path: Path) -> str:
    """Write minimal PNG-like bytes and return the path."""
    path = tmp_path / "fake.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\nMINIMAL")
    return str(path)


def _run_main_with_args(argv: list[str]) -> int:
    """Invoke main() with a custom argv; return exit code (or re-raise)."""
    from generated_agent.__main__ import main  # noqa: PLC0415

    with patch("sys.argv", ["generated-agent", *argv]):
        return main()


def test_main_aborts_on_empty_exam_list(
    fake_image: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """T014 / AC2 — empty pre-OCR list aborts with exit 4 + E_OCR_UNKNOWN_IMAGE.

    Invariant: runner.run_async must NOT be invoked (the LlmAgent never
    sees the image path).
    """
    runner_spy = MagicMock(name="runner.run_async.spy")

    async def _preocr_empty(*_args: Any, **_kwargs: Any) -> list[str]:
        return []

    with (
        patch("generated_agent.__main__._run_preocr", side_effect=_preocr_empty, create=True),
        patch("generated_agent.__main__._run_agent", runner_spy, create=True),
        pytest.raises(SystemExit) as exc_info,
    ):
        _run_main_with_args(["--image", fake_image])

    assert exc_info.value.code == 4, f"expected exit 4, got {exc_info.value.code}"
    assert runner_spy.call_count == 0, "LlmAgent runner must not be invoked on empty exam list"

    captured = capsys.readouterr()
    stderr_line = captured.err.strip().splitlines()[-1]
    envelope = json.loads(stderr_line)
    assert envelope["error"]["code"] == "E_OCR_UNKNOWN_IMAGE"


def test_main_aborts_on_mcp_unavailable(
    fake_image: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """T015 / AC6 — _PreOcrError(E_MCP_UNAVAILABLE) aborts with exit 5.

    Invariant: runner.run_async must NOT be invoked.
    """
    from generated_agent.preocr import _PreOcrError  # noqa: PLC0415 — RED import

    runner_spy = MagicMock(name="runner.run_async.spy")

    async def _preocr_down(*_args: Any, **_kwargs: Any) -> list[str]:
        raise _PreOcrError(
            code="E_MCP_UNAVAILABLE",
            message="OCR MCP unavailable",
            hint="docker compose ps",
        )

    with (
        patch("generated_agent.__main__._run_preocr", side_effect=_preocr_down, create=True),
        patch("generated_agent.__main__._run_agent", runner_spy, create=True),
        pytest.raises(SystemExit) as exc_info,
    ):
        _run_main_with_args(["--image", fake_image])

    assert exc_info.value.code == 5, f"expected exit 5, got {exc_info.value.code}"
    assert runner_spy.call_count == 0, "LlmAgent runner must not be invoked on MCP unavailable"

    captured = capsys.readouterr()
    stderr_line = captured.err.strip().splitlines()[-1]
    envelope = json.loads(stderr_line)
    assert envelope["error"]["code"] == "E_MCP_UNAVAILABLE"
