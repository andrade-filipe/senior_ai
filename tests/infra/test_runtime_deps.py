"""Regression guard: runtime deps live in [project].dependencies, not dev groups.

Context: on 2026-04-19 a Docker container crashed at startup with
`ImportError: cannot import name 'make_pii_callback' from 'security'`.
Root cause: `security` was declared in generated_agent/pyproject.toml under
`[dependency-groups].dev`, but Dockerfiles use `uv pip install --system .`
which installs ONLY `[project].dependencies`. The dev group is never installed
inside the image, so the runtime import fails at container start.

Invariant enforced here: packages whose imports are exercised at container
runtime (not only in tests) MUST appear in `[project].dependencies`.
"""

from __future__ import annotations

import pathlib
import tomllib

REPO_ROOT = pathlib.Path(__file__).parent.parent.parent


def _project_deps(pkg: str) -> set[str]:
    pyproject = REPO_ROOT / pkg / "pyproject.toml"
    assert pyproject.exists(), f"{pkg}/pyproject.toml missing"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    return set(data.get("project", {}).get("dependencies", []))


def _dev_deps(pkg: str) -> set[str]:
    pyproject = REPO_ROOT / pkg / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    groups = data.get("dependency-groups", {}) or {}
    return set(groups.get("dev", []))


def _starts_with(deps: set[str], name: str) -> bool:
    """True if any dep string starts with `name` (handles version specifiers)."""
    return any(d == name or d.startswith(f"{name}>") or d.startswith(f"{name}<")
               or d.startswith(f"{name}=") or d.startswith(f"{name}~")
               or d.startswith(f"{name}!") or d.startswith(f"{name};")
               or d.startswith(f"{name} ") for d in deps)


def test_generated_agent_security_is_runtime() -> None:
    """`security` (PII Layer 2 callback, ADR-0003) must be a runtime dep."""
    project = _project_deps("generated_agent")
    assert _starts_with(project, "security"), (
        "security must be in generated_agent/pyproject.toml [project].dependencies "
        "— it is imported at container runtime by before_model_callback (ADR-0003). "
        f"Current [project].dependencies: {sorted(project)}"
    )


def test_generated_agent_security_not_only_in_dev() -> None:
    """Guard: security must not appear exclusively in [dependency-groups].dev."""
    project = _project_deps("generated_agent")
    dev = _dev_deps("generated_agent")
    if _starts_with(dev, "security") and not _starts_with(project, "security"):
        raise AssertionError(
            "security present only in dev group — Docker `uv pip install --system .` "
            "will not install it, and runtime import of make_pii_callback will fail."
        )


def test_ocr_mcp_security_is_runtime() -> None:
    """ocr_mcp also imports security.pii_mask at runtime (Layer 1)."""
    project = _project_deps("ocr_mcp")
    assert _starts_with(project, "security"), (
        "security must be in ocr_mcp/pyproject.toml [project].dependencies "
        "— ocr_mcp/server.py applies PII Layer 1 masking before returning text. "
        f"Current [project].dependencies: {sorted(project)}"
    )
