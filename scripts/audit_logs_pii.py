#!/usr/bin/env python3
"""PII audit script for compose log output.

Reads log content from stdin OR from --log-file path and scans every line
against PII patterns defined in docs/ARCHITECTURE.md § "Lista definitiva de
entidades PII" (ADR-0008 § Logging sem PII crua, AC14).

Output (stdout):
    JSON object: {"matches": N, "samples": [{"pattern": ..., "line_preview": "..."}, ...]}

Exit codes:
    0 — no PII patterns found (logs are clean)
    1 — one or more PII patterns found (CI should fail)
    2 — usage error (bad arguments, unreadable file)

Patterns (raw regex strings):
    BR_CPF          r'\d{3}[.]\d{3}[.]\d{3}-\d{2}'
    BR_CNPJ         r'\d{2}[.]\d{3}[.]\d{3}/\d{4}-\d{2}'
    BR_RG           r'\d{1,2}[.]\d{3}[.]\d{3}-[0-9Xx]'
    BR_PHONE        r'[(]\d{2}[)]\s?\d{4,5}-\d{4}'
    EMAIL_ADDRESS   r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+[.][A-Za-z]{2,}'

With --strict flag (off by default to avoid false positives from 11-digit IDs):
    BR_CPF_RAW      r'(?<![0-9])\d{11}(?![0-9])'

Usage:
    python scripts/audit_logs_pii.py --log-file /tmp/compose_logs.log
    docker compose logs | python scripts/audit_logs_pii.py
    docker compose logs | python scripts/audit_logs_pii.py --strict
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import TypedDict

# ---------------------------------------------------------------------------
# PII patterns (docs/ARCHITECTURE.md § "Lista definitiva de entidades PII")
# ---------------------------------------------------------------------------

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("BR_CPF", re.compile(r"\d{3}\.\d{3}\.\d{3}-\d{2}")),
    ("BR_CNPJ", re.compile(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}")),
    ("BR_RG", re.compile(r"\d{1,2}\.\d{3}\.\d{3}-[0-9Xx]")),
    ("BR_PHONE", re.compile(r"\(\d{2}\)\s?\d{4,5}-\d{4}")),
    ("EMAIL_ADDRESS", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
]

# Strict-mode pattern: raw 11-digit CPF (off by default to avoid false positives
# from UUIDs, request IDs, and other 11-digit sequences)
_STRICT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("BR_CPF_RAW", re.compile(r"(?<!\d)\d{11}(?!\d)")),
]

# Maximum length for a line_preview in the output JSON
_PREVIEW_MAX_LEN = 120

# Maximum number of samples to report (avoids huge JSON on noisy logs)
_MAX_SAMPLES = 20


class PiiSample(TypedDict):
    pattern: str
    line_preview: str


def _build_patterns(strict: bool) -> list[tuple[str, re.Pattern[str]]]:
    patterns = list(_PATTERNS)
    if strict:
        patterns.extend(_STRICT_PATTERNS)
    return patterns


def audit(text: str, strict: bool = False) -> dict:
    """Scan ``text`` for PII patterns and return a result dict.

    Args:
        text:   Log content as a single string (newline-separated lines).
        strict: When True, also scan for raw 11-digit CPF sequences.

    Returns:
        dict with keys:
            matches (int)       — total number of matching lines found.
            samples (list)      — up to _MAX_SAMPLES dicts with keys
                                  ``pattern`` and ``line_preview``.
    """
    patterns = _build_patterns(strict)
    matches = 0
    samples: list[PiiSample] = []

    for line in text.splitlines():
        for name, pattern in patterns:
            if pattern.search(line):
                matches += 1
                if len(samples) < _MAX_SAMPLES:
                    preview = line[:_PREVIEW_MAX_LEN]
                    if len(line) > _PREVIEW_MAX_LEN:
                        preview += "…"
                    samples.append({"pattern": name, "line_preview": preview})

    return {"matches": matches, "samples": samples}


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Returns:
        0 if no PII found, 1 if PII found, 2 on usage error.
    """
    parser = argparse.ArgumentParser(
        prog="audit_logs_pii",
        description=(
            "Audit compose log output for PII patterns (ADR-0008, AC14). "
            "Reads from --log-file or stdin."
        ),
    )
    parser.add_argument(
        "--log-file",
        metavar="PATH",
        help="Path to log file. When omitted, reads from stdin.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help=(
            "Also scan for raw 11-digit CPF sequences (higher false-positive risk "
            "— disable when logs contain long numeric request IDs)."
        ),
    )
    args = parser.parse_args(argv)

    if args.log_file:
        try:
            with open(args.log_file, encoding="utf-8", errors="replace") as fh:
                content = fh.read()
        except OSError as exc:
            print(
                json.dumps({"error": f"Cannot read {args.log_file}: {exc}"}),
                file=sys.stdout,
            )
            return 2
    else:
        content = sys.stdin.read()

    result = audit(content, strict=args.strict)
    print(json.dumps(result, ensure_ascii=False))
    return 1 if result["matches"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
