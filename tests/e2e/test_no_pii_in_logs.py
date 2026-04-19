"""PII audit tests for compose service logs (AC14).

Two test classes:
  1. TestAuditScriptSelfTest (no marker — always runs):
       Validates that the audit script itself correctly detects planted PII.
       This guards against a silent audit failure (the "test the test" pattern).

  2. TestNoPiiInComposeLogs (e2e_ci marker):
       After compose stack is running and the CI flow tests have exercised the
       API, captures all service logs and runs the audit script.  Asserts exit
       code 0 and matches == 0.

Covers AC14 (ADR-0008 § Logging sem PII crua).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
AUDIT_SCRIPT = REPO_ROOT / "scripts" / "audit_logs_pii.py"


# ---------------------------------------------------------------------------
# Unit-style self-test (no marker — always runs in every pytest invocation)
# ---------------------------------------------------------------------------


class TestAuditScriptSelfTest:
    """Validates that audit_logs_pii.py correctly detects known PII patterns."""

    def test_audit_script_detects_planted_cpf(self) -> None:
        """Feed a line with a CPF; assert exit 1 and at least one BR_CPF match.

        Note: a CPF string like '123.456.789-00' may also trigger the BR_RG
        pattern (r'\\d{1,2}\\.\\d{3}\\.\\d{3}-[0-9Xx]') as a partial sub-match.
        This is conservative (more false positives, fewer false negatives) and
        is the correct behavior for a security audit script.
        The test therefore asserts >= 1 match and that BR_CPF is among them.
        """
        log_with_pii = "patient CPF: 123.456.789-00 registered\n"

        result = subprocess.run(
            [sys.executable, str(AUDIT_SCRIPT)],
            input=log_with_pii,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, (
            f"Audit script should exit 1 when PII found; got {result.returncode}. "
            f"stdout: {result.stdout}"
        )
        data = json.loads(result.stdout)
        assert data["matches"] >= 1, (
            f"Expected >= 1 match, got {data['matches']}. Data: {data}"
        )
        patterns_found = {s["pattern"] for s in data["samples"]}
        assert "BR_CPF" in patterns_found, (
            f"Expected BR_CPF in patterns found; got {patterns_found}"
        )

    def test_audit_script_clean_logs_exit_zero(self) -> None:
        """Feed log lines with no PII; assert exit 0 and matches == 0."""
        clean_log = (
            '{"ts": "2026-04-19T12:00:00.000Z", "level": "INFO", '
            '"service": "scheduling-api", "correlation_id": "api-abc123", '
            '"event": "http.request", "method": "POST", '
            '"path": "/api/v1/appointments", "status_code": 201}\n'
        )

        result = subprocess.run(
            [sys.executable, str(AUDIT_SCRIPT)],
            input=clean_log,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Audit script should exit 0 for clean logs; got {result.returncode}. "
            f"stdout: {result.stdout}"
        )
        data = json.loads(result.stdout)
        assert data["matches"] == 0, (
            f"Expected 0 matches for clean log, got {data['matches']}. Data: {data}"
        )

    def test_audit_script_detects_planted_email(self) -> None:
        """Feed a line with an email address; assert exit 1 and pattern == EMAIL_ADDRESS."""
        log_with_email = "User joao.silva@example.com logged in\n"

        result = subprocess.run(
            [sys.executable, str(AUDIT_SCRIPT)],
            input=log_with_email,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, (
            f"Audit script should exit 1 for email PII; got {result.returncode}"
        )
        data = json.loads(result.stdout)
        assert data["matches"] >= 1
        patterns_found = {s["pattern"] for s in data["samples"]}
        assert "EMAIL_ADDRESS" in patterns_found, (
            f"Expected EMAIL_ADDRESS in patterns; got {patterns_found}"
        )

    def test_audit_script_detects_br_phone(self) -> None:
        """Feed a line with a BR phone number; assert exit 1."""
        log_with_phone = "contact: (11) 99999-1234 for scheduling\n"

        result = subprocess.run(
            [sys.executable, str(AUDIT_SCRIPT)],
            input=log_with_phone,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, (
            f"Audit script should exit 1 for BR_PHONE; got {result.returncode}"
        )
        data = json.loads(result.stdout)
        assert data["matches"] >= 1

    def test_audit_script_log_file_flag(self, tmp_path) -> None:
        """--log-file flag reads from file instead of stdin.

        CPF '987.654.321-00' may also match BR_RG as a partial sub-match, so
        we assert >= 1 match (conservative security audit behavior).
        """
        log_file = tmp_path / "test.log"
        log_file.write_text("CPF: 987.654.321-00\n", encoding="utf-8")

        result = subprocess.run(
            [sys.executable, str(AUDIT_SCRIPT), "--log-file", str(log_file)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        data = json.loads(result.stdout)
        assert data["matches"] >= 1


# ---------------------------------------------------------------------------
# E2E audit — requires compose_stack fixture (e2e_ci marker)
# ---------------------------------------------------------------------------


@pytest.mark.e2e_ci
class TestNoPiiInComposeLogs:
    """[AC14] After E2E CI run: all compose logs must have zero PII matches."""

    def test_audit_logs_pii_zero_matches(self, compose_stack: None) -> None:
        """Collect all compose service logs and assert audit_logs_pii exits 0.

        Post-condition:
          - audit script exit code == 0
          - result["matches"] == 0

        If this test fails: a service emitted raw PII (CPF, CNPJ, RG, phone,
        or e-mail) in its log output.  Investigate the offending line shown in
        result["samples"] and fix the logging call in the responsible service.
        """
        from .conftest import collect_compose_logs

        logs = collect_compose_logs()  # all services

        result = subprocess.run(
            [sys.executable, str(AUDIT_SCRIPT)],
            input=logs,
            capture_output=True,
            text=True,
        )
        data = json.loads(result.stdout)

        assert result.returncode == 0, (
            f"[AC14] PII found in compose logs! matches={data['matches']}. "
            f"Samples:\n"
            + "\n".join(
                f"  pattern={s['pattern']}: {s['line_preview']}"
                for s in data.get("samples", [])
            )
        )
        assert data["matches"] == 0, (
            f"[AC14] audit_logs_pii reported {data['matches']} PII match(es). "
            f"Samples: {data['samples']}"
        )
