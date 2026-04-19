"""Helper script to generate and hash the OCR fixture PNG.

Run: uv run python tests/generate_fixture.py
Prints the SHA-256 hash to update FIXTURES in ocr_mcp/fixtures.py.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

# Add tests dir to path so conftest helpers work standalone
sys.path.insert(0, str(Path(__file__).parent))

from conftest import SAMPLE_PNG, _generate_fixture_png  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate OCR fixture PNG and print hash")
    parser.add_argument("--print-hash", action="store_true", help="Print SHA-256 hash and exit")
    args = parser.parse_args()

    if not SAMPLE_PNG.exists():
        print(f"Generating {SAMPLE_PNG} ...")
        _generate_fixture_png(SAMPLE_PNG)
        print(f"Generated: {SAMPLE_PNG}")

    with open(SAMPLE_PNG, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()

    print(f"SHA-256: {digest}")

    if args.print_hash:
        sys.exit(0)

    print("\nUpdate ocr_mcp/fixtures.py SAMPLE_MEDICAL_ORDER_HASH with this value.")


if __name__ == "__main__":
    main()
