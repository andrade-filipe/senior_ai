"""Infra tests — Dockerfile compliance (AC1–AC5, AC15).

yaml/regex-based assertions run without Docker.
@pytest.mark.infra tests require a live Docker daemon; skip them in the
normal unit pass with:  pytest tests/infra -m "not infra"
"""

from __future__ import annotations

import pathlib
import re
import subprocess

import pytest

REPO_ROOT = pathlib.Path(__file__).parent.parent.parent

# Services that must have a Dockerfile
DOCKERFILES: dict[str, pathlib.Path] = {
    "ocr_mcp": REPO_ROOT / "ocr_mcp" / "Dockerfile",
    "rag_mcp": REPO_ROOT / "rag_mcp" / "Dockerfile",
    "scheduling_api": REPO_ROOT / "scheduling_api" / "Dockerfile",
    "generated_agent": REPO_ROOT / "generated_agent" / "Dockerfile",
}

# Services that must expose an HTTP port and therefore require HEALTHCHECK
HEALTHCHECK_REQUIRED = {"ocr_mcp", "rag_mcp", "scheduling_api"}


def _read(path: pathlib.Path) -> str:
    """Read Dockerfile text; fail with clear message if missing."""
    assert path.exists(), f"Dockerfile missing: {path}"
    return path.read_text(encoding="utf-8")


class TestDockerfileAC1BaseImage:
    """[AC1] Every Dockerfile declares python:3.12-slim as base image."""

    @pytest.mark.parametrize("service,path", list(DOCKERFILES.items()))
    def test_base_image(self, service: str, path: pathlib.Path) -> None:
        content = _read(path)
        assert "FROM python:3.12-slim" in content, (
            f"[AC1] {service}/Dockerfile must use 'FROM python:3.12-slim'; found:\n"
            + "\n".join(line for line in content.splitlines() if line.startswith("FROM"))
        )


class TestDockerfileAC2UvInstall:
    """[AC2] Every Dockerfile installs deps via uv pip install --system (ADR-0005)."""

    @pytest.mark.parametrize("service,path", list(DOCKERFILES.items()))
    def test_uv_pip_install_system(self, service: str, path: pathlib.Path) -> None:
        content = _read(path)
        assert "uv pip install --system" in content, (
            f"[AC2] {service}/Dockerfile must use 'uv pip install --system'; "
            "NOT 'uv sync' or plain 'pip install'."
        )
        # Negative: must NOT use 'uv sync' (ADR-0005 mandates uv pip install --system)
        # Allow 'uv sync' in comments but not as a RUN command
        run_lines = [
            line.strip()
            for line in content.splitlines()
            if re.match(r"^\s*RUN\b", line)
        ]
        for run_line in run_lines:
            assert "uv sync" not in run_line, (
                f"[AC2] {service}/Dockerfile must NOT use 'uv sync' in RUN; "
                f"found: {run_line!r}"
            )


class TestDockerfileAC3CmdExecForm:
    """[AC3] CMD/ENTRYPOINT uses exec/list form — never shell form string.

    Either a standalone CMD or a standalone ENTRYPOINT satisfies the rule; the
    generated-agent image uses ENTRYPOINT so runtime args like `--image <path>`
    append to the module invocation instead of replacing it.
    The HEALTHCHECK CMD argument is a separate concern (AC15).
    """

    @pytest.mark.parametrize("service,path", list(DOCKERFILES.items()))
    def test_cmd_exec_form(self, service: str, path: pathlib.Path) -> None:
        content = _read(path)
        # Standalone CMD/ENTRYPOINT instructions start at column 0 (no indent)
        # and are NOT continuations of a HEALTHCHECK line (HEALTHCHECK lines use
        # backslash-continuation, so the inner CMD token is indented).
        exec_lines = [
            line.strip()
            for line in content.splitlines()
            if re.match(r"^(CMD|ENTRYPOINT)\b", line)
        ]
        assert exec_lines, (
            f"[AC3] {service}/Dockerfile has no CMD or ENTRYPOINT instruction."
        )
        for exec_line in exec_lines:
            assert exec_line.startswith(("CMD [", "ENTRYPOINT [")), (
                f"[AC3] {service}/Dockerfile must use exec (list) form "
                f"(CMD [...] or ENTRYPOINT [...]); found: {exec_line!r}"
            )


class TestDockerfileAC15HealthcheckExplicit:
    """[AC15] HEALTHCHECK must declare --interval, --timeout, --retries, --start-period.

    Invariant: no implicit defaults (ADR-0008).
    Only services that expose HTTP require HEALTHCHECK.
    """

    @pytest.mark.parametrize("service", list(HEALTHCHECK_REQUIRED))
    def test_healthcheck_has_all_fields(self, service: str) -> None:
        path = DOCKERFILES[service]
        content = _read(path)
        hc_lines = [
            line
            for line in content.splitlines()
            if "HEALTHCHECK" in line
        ]
        assert hc_lines, (
            f"[AC15] {service}/Dockerfile must declare a HEALTHCHECK instruction."
        )
        combined = " ".join(hc_lines)
        for flag in ("--interval=", "--timeout=", "--retries=", "--start-period="):
            assert flag in combined, (
                f"[AC15] {service}/Dockerfile HEALTHCHECK missing {flag!r}. "
                "All four fields must be explicit (ADR-0008 § Timeouts)."
            )


class TestSpacyModelBakedForPii:
    """[ADR-0003 addendum, 2026-04-19] Dockerfiles that run Presidio must bake
    the pt_core_news_lg spaCy model at build time.

    Context: runtime first-call download (~568 MB) trips the 5 s PII guard
    timeout → E_PII_TIMEOUT → pii.callback.error → prompt corrupted → agent
    output invalid. Observed in the 2026-04-19 E2E run.

    Services that need the bake:
      - ocr_mcp       — applies PII Layer 1 mask in the SSE tool response
      - generated_agent — applies PII Layer 2 via before_model_callback
    rag_mcp does NOT run Presidio and therefore does not need the model.
    """

    SPACY_REQUIRED = {"ocr_mcp", "generated_agent"}

    @pytest.mark.parametrize("service", sorted(SPACY_REQUIRED))
    def test_spacy_model_baked(self, service: str) -> None:
        content = _read(DOCKERFILES[service])
        # ADR-0009 (K2): Dockerfiles now use ARG PII_SPACY_MODEL_PT=pt_core_news_lg
        # so the model can be swapped at build time via docker-compose build.args.
        # Accept either the legacy literal form OR the new ARG-backed form.
        literal_form = "python -m spacy download pt_core_news_lg" in content
        arg_form = (
            "ARG PII_SPACY_MODEL_PT" in content
            and "python -m spacy download $PII_SPACY_MODEL_PT" in content
        )
        assert literal_form or arg_form, (
            f"[ADR-0003] {service}/Dockerfile must bake the spaCy model at build time. "
            "Expected either:\n"
            "  (legacy)  RUN python -m spacy download pt_core_news_lg\n"
            "  (ADR-0009) ARG PII_SPACY_MODEL_PT=pt_core_news_lg + "
            "RUN python -m spacy download $PII_SPACY_MODEL_PT\n"
            "Runtime download would trip the 5 s PII guard timeout."
        )
        # The ARG must declare pt_core_news_lg as default so an operator who
        # does NOT override it still gets a working image out-of-the-box.
        if arg_form and not literal_form:
            assert "ARG PII_SPACY_MODEL_PT=pt_core_news_lg" in content, (
                f"[ADR-0003] {service}/Dockerfile ARG PII_SPACY_MODEL_PT must default "
                "to pt_core_news_lg so the image works without an explicit build arg."
            )

    def test_rag_mcp_does_not_need_spacy(self) -> None:
        """rag_mcp does not run Presidio — guard against unnecessary image bloat."""
        content = _read(DOCKERFILES["rag_mcp"])
        assert "spacy download" not in content, (
            "rag_mcp/Dockerfile should NOT bake pt_core_news_lg — "
            "rag_mcp does not run Presidio (adds ~568 MB with no benefit)."
        )


@pytest.mark.infra
class TestDockerfileBuilds:
    """[AC5] Each Dockerfile builds successfully with docker build.

    Requires a live Docker daemon.  Skip with: pytest -m "not infra"
    """

    @pytest.mark.parametrize("service,path", list(DOCKERFILES.items()))
    def test_each_dockerfile_builds(self, service: str, path: pathlib.Path) -> None:
        tag = f"senior-ia-{service.replace('_', '-')}:ci-test"
        result = subprocess.run(
            ["docker", "build", "-t", tag, "-f", str(path), str(REPO_ROOT)],
            capture_output=True,
            text=True,
            timeout=600,
        )
        assert result.returncode == 0, (
            f"[AC5] docker build failed for {service}:\n"
            f"STDOUT:\n{result.stdout[-2000:]}\n"
            f"STDERR:\n{result.stderr[-2000:]}"
        )
