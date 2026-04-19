"""Transpiler CLI — python -m transpiler <spec.json> [-o <dir>] [-v].

Exit codes (per spec 0002 § Requisitos não-funcionais and ADR-0008):
    0  — success
    1  — E_TRANSPILER_SCHEMA   (spec validation failure)
    2  — E_TRANSPILER_RENDER or E_TRANSPILER_RENDER_SIZE   (render failure)
    3  — E_TRANSPILER_SYNTAX   (ast.parse rejected generated output)
    4  — unexpected error (should not happen; bug report)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from transpiler.errors import ChallengeError, TranspilerError, format_challenge_error
from transpiler.generator import render
from transpiler.schema import load_spec

# ---------------------------------------------------------------------------
# Exit-code mapping (stable contract with callers and tests)
# ---------------------------------------------------------------------------

_EXIT_CODE: dict[str, int] = {
    "E_TRANSPILER_SCHEMA": 1,
    "E_TRANSPILER_RENDER": 2,
    "E_TRANSPILER_RENDER_SIZE": 2,
    "E_TRANSPILER_SYNTAX": 3,
}
_EXIT_UNEXPECTED = 4


# ---------------------------------------------------------------------------
# Path traversal guard
# ---------------------------------------------------------------------------


def _validate_output_dir(raw: str) -> Path:
    """Resolve and validate that output_dir is within the current working directory.

    Pre:
        raw is a non-empty string provided by the user on the command line.
    Post:
        Returns a resolved Path that is relative to Path.cwd().

    Args:
        raw: Raw --output argument value from argparse.

    Returns:
        Resolved output directory Path.

    Raises:
        TranspilerError: with code='E_TRANSPILER_RENDER' when the resolved path
            is outside the current working directory (path traversal, AC11).
    """
    resolved = Path(raw).resolve()
    cwd = Path.cwd().resolve()

    try:
        resolved.relative_to(cwd)
    except ValueError as exc:
        raise TranspilerError(
            code="E_TRANSPILER_RENDER",
            message=(
                f"output_dir fora do projeto: '{resolved}' não está dentro de '{cwd}'. "
                "Escolha um diretório dentro do diretório de trabalho atual."
            ),
            hint=(
                "Use um caminho relativo (ex.: -o ./out) ou absoluto dentro do projeto. "
                "Caminhos como '../../etc' ou '/etc' são rejeitados (AC11)."
            ),
            path=raw,
            context={"resolved": str(resolved), "cwd": str(cwd)},
        ) from exc

    return resolved


# ---------------------------------------------------------------------------
# stderr formatting
# ---------------------------------------------------------------------------


def _print_error(exc: ChallengeError) -> None:
    """Print a ChallengeError in canonical line-per-field format to stderr.

    Format per ADR-0008 § Shape canônico (CLI variant): one line per field.

    Args:
        exc: Any ChallengeError instance to serialize.
    """
    payload = format_challenge_error(exc)
    for key, value in payload.items():
        if value is not None:
            print(f"{key}: {value}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the argparse ArgumentParser for the transpiler CLI.

    Returns:
        Configured ArgumentParser with spec_path, --output, --verbose flags.
    """
    parser = argparse.ArgumentParser(
        prog="python -m transpiler",
        description=(
            "Transpilador JSON para pacote Python ADK. "
            "Le um spec.json validado e gera generated_agent/ com agent.py, "
            "__init__.py, requirements.txt, Dockerfile e .env.example."
        ),
    )
    parser.add_argument(
        "spec_path",
        metavar="spec.json",
        help="Caminho para o arquivo spec.json (UTF-8, max 1 MB).",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="DIR",
        default=".",
        help=(
            "Diretório de saída onde generated_agent/ será criado "
            "(padrão: diretório atual). Deve estar dentro do cwd."
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Ativa saída detalhada (lista arquivos gerados).",
    )
    return parser


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the transpiler.

    Pre:
        argv is a list of command-line arguments (defaults to sys.argv[1:]).
    Post:
        Returns an integer exit code (0 on success, 1/2/3/4 on error).
        On error, prints canonical error shape to stderr before returning.

    Args:
        argv: Optional argument list for testing. When None, sys.argv[1:] is used.

    Returns:
        Integer exit code per the spec (0 ok, 1 schema, 2 render, 3 syntax, 4 unexpected).
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        output_dir = _validate_output_dir(args.output)
        spec = load_spec(args.spec_path)
        render(spec, output_dir)
    except TranspilerError as exc:
        _print_error(exc)
        return _EXIT_CODE.get(exc.code, _EXIT_UNEXPECTED)
    except ChallengeError as exc:
        _print_error(exc)
        return _EXIT_UNEXPECTED
    except Exception as exc:  # noqa: BLE001  # final safety net — never let unhandled exception escape CLI
        unexpected = TranspilerError(
            code="E_TRANSPILER_RENDER",
            message=f"Erro inesperado: {exc}",
            hint="Abra issue com o stack trace completo.",
        )
        _print_error(unexpected)
        return _EXIT_UNEXPECTED

    if args.verbose:
        dest = output_dir / "generated_agent"
        print(f"Gerado em: {dest}", file=sys.stdout)
        for f in sorted(dest.iterdir()):
            print(f"  {f.name}", file=sys.stdout)

    return 0
