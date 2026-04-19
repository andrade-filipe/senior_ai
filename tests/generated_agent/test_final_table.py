"""Test AC17 / T026: ASCII table snapshot.

Green in this wave (unit — pure function, no Docker required).
"""

from __future__ import annotations

from datetime import datetime


def test_ascii_table_snapshot() -> None:
    """AC17 / T026: format_ascii_table produces the expected ASCII layout.

    The golden output is inlined here (no pytest-regressions dep needed).
    Format matches the literal spec in AC17.
    """
    from generated_agent.__main__ import format_ascii_table

    rows = [
        ("Hemograma Completo", "HMG-001", 0.98, False),
        ("Glicemia de Jejum", "GLJ-002", 0.95, False),
    ]
    sched = datetime(2026, 5, 1, 9, 0, 0)
    result = format_ascii_table(rows, "apt-42", sched)

    lines = result.splitlines()

    # Structure: separator, header, separator, row*N, separator, footer
    assert lines[0].startswith("+"), "First line must be a separator"
    assert "Exame" in lines[1], f"Header row must contain 'Exame', got: {lines[1]}"
    assert lines[2].startswith("+"), "Third line must be a separator after header"

    # Data rows
    assert "Hemograma Completo" in lines[3]
    assert "HMG-001" in lines[3]
    assert "Glicemia de Jejum" in lines[4]
    assert "GLJ-002" in lines[4]

    # Separator after data rows
    assert lines[5].startswith("+")

    # Footer line with appointment ID
    footer = lines[6]
    assert "apt-42" in footer, f"Footer must contain appointment ID, got: {footer}"
    assert "2026-05-01" in footer, f"Footer must contain scheduled date, got: {footer}"


def test_ascii_table_inconclusive_marker() -> None:
    """AC10: inconclusive exam has '?' appended to its code in the table."""
    from generated_agent.__main__ import format_ascii_table

    rows = [
        ("Exame Incerto", "EI-999", 0.60, True),
    ]
    result = format_ascii_table(rows, "apt-1", datetime(2026, 5, 1))
    assert "EI-999?" in result, f"Inconclusive exam must have '?', got:\n{result}"


def test_ascii_table_no_ansi() -> None:
    """AC17: table must contain no ANSI escape sequences."""
    import re

    from generated_agent.__main__ import format_ascii_table

    rows = [("Hemograma", "HMG-001", 0.98, False)]
    result = format_ascii_table(rows, "apt-1", datetime(2026, 5, 1))

    ansi_pattern = re.compile(r"\x1b\[[0-9;]*m")
    assert not ansi_pattern.search(result), "Table must not contain ANSI escape codes"


def test_ascii_table_no_rich() -> None:
    """AC17: Rich markup must not appear in the table."""
    from generated_agent.__main__ import format_ascii_table

    rows = [("Hemograma", "HMG-001", 0.98, False)]
    result = format_ascii_table(rows, "apt-1", datetime(2026, 5, 1))
    assert "[bold]" not in result
    assert "[/bold]" not in result
