"""Guard: .env.example covers all env keys mandated by ADR-0009.

This test fails if:
  - Any key from the ADR-0009 ENV surface is absent from .env.example, OR
  - The .env.example file does not exist.

It does NOT assert default values — only that the key appears in the file.
This ensures operators/evaluators can discover every tunable in one place.

Run:
    cd <repo-root> && uv run pytest tests/infra/test_env_config.py -v
"""

from __future__ import annotations

import pathlib
import re

# ---------------------------------------------------------------------------
# Repository root anchor
# ---------------------------------------------------------------------------

REPO = pathlib.Path(__file__).parent.parent.parent
ENV_EXAMPLE = REPO / ".env.example"

# ---------------------------------------------------------------------------
# Complete ADR-0009 ENV surface (19 new vars; existing vars included for
# completeness of the guard — see ADR-0009 Table ENV).
# ---------------------------------------------------------------------------

EXPECTED_KEYS: list[str] = [
    # --- Agent runtime (generated_agent) ---
    "GEMINI_MODEL",
    "AGENT_TIMEOUT_SECONDS",
    "SCHEDULING_OPENAPI_FETCH_TIMEOUT_SECONDS",
    # --- Scheduling API ---
    "SCHEDULING_REQUEST_TIMEOUT_SECONDS",
    "SCHEDULING_BODY_SIZE_LIMIT_BYTES",
    # --- OCR MCP ---
    "OCR_IMAGE_MAX_BYTES",
    "OCR_TIMEOUT_SECONDS",
    "OCR_DEFAULT_LANGUAGE",
    # --- RAG MCP ---
    "RAG_QUERY_MAX_CHARS",
    "RAG_SEARCH_TIMEOUT_SECONDS",
    "RAG_FUZZY_THRESHOLD",
    "RAG_CATALOG_PATH",
    # --- PII guard ---
    "PII_TEXT_MAX_BYTES",
    "PII_CALLBACK_TEXT_MAX_BYTES",
    "PII_ALLOW_LIST_MAX",
    "PII_TIMEOUT_SECONDS",
    "PII_SCORE_THRESHOLD",
    "PII_SPACY_MODEL_PT",
    "PII_SPACY_MODEL_EN",
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_env_example_exists() -> None:
    """[ADR-0009] .env.example must exist at the repository root."""
    assert ENV_EXAMPLE.exists(), (
        f"[ADR-0009] .env.example not found at {ENV_EXAMPLE}. "
        "Run the devops-engineer to generate it."
    )
    assert ENV_EXAMPLE.stat().st_size > 0, (
        f"[ADR-0009] .env.example is empty (0 bytes)."
    )


def test_env_example_covers_adr_0009_surface() -> None:
    """[ADR-0009] .env.example must contain all 19 env keys from the ADR-0009 ENV table.

    Pattern: each key must appear as `KEY=` at the beginning of a line
    (allowing for commented-out examples like `# KEY=default` is intentional
    — the check uses a line-start pattern so both `KEY=` and `# KEY=` match,
    guaranteeing the key is at least documented even when commented out).
    We require the bare `KEY=` form (uncommented) because the file is meant
    to be copied and edited, not merely a reference.
    """
    content = ENV_EXAMPLE.read_text(encoding="utf-8")
    # Prepend newline so the pattern `\nKEY=` works for the first line too
    searchable = "\n" + content

    missing = [k for k in EXPECTED_KEYS if f"\n{k}=" not in searchable]

    assert not missing, (
        f"[ADR-0009] The following env keys are missing from .env.example "
        f"(must appear as KEY=<value> on a line): {missing}\n"
        f"Add them to {ENV_EXAMPLE} with a comment explaining their purpose."
    )


def test_env_example_no_real_secrets() -> None:
    """[ADR-0009] .env.example must not contain a real Google API key.

    Real keys start with 'AIza' (Google's public prefix). A placeholder like
    '<your-google-api-key>' or 'your_key_here' is acceptable.
    """
    content = ENV_EXAMPLE.read_text(encoding="utf-8")
    # Real Google API keys start with AIza followed by alphanumeric chars
    real_key_pattern = re.compile(r"GOOGLE_API_KEY\s*=\s*AIza[A-Za-z0-9_\-]{30,}")
    match = real_key_pattern.search(content)
    assert match is None, (
        f"[ADR-0009] .env.example appears to contain a real GOOGLE_API_KEY "
        f"(starts with 'AIza...'). Replace it with a placeholder like "
        f"'<your-google-api-key>' before committing."
    )
