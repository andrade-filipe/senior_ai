"""Shared pytest fixtures for OCR MCP tests.

NOTE: The sample_medical_order.png fixture is generated automatically on first run
if it doesn't exist. It contains a fake CPF (111.444.777-35) and fake patient
name to exercise PII masking (AC4, T013).
"""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixture paths
# ---------------------------------------------------------------------------
FIXTURE_DIR = Path(__file__).parent / "fixtures"
SAMPLE_PNG = FIXTURE_DIR / "sample_medical_order.png"


# Auto-generate fixture PNG before tests run if it doesn't exist
def pytest_configure(config: object) -> None:
    """Generate the sample PNG fixture if it doesn't exist."""
    if not SAMPLE_PNG.exists():
        _generate_fixture_png(SAMPLE_PNG)


@pytest.fixture(scope="session")
def fixture_dir() -> Path:
    """Return the path to the test fixtures directory."""
    return FIXTURE_DIR


@pytest.fixture(scope="session")
def sample_png_path() -> Path:
    """Return the path to sample_medical_order.png fixture."""
    return SAMPLE_PNG


@pytest.fixture(scope="session")
def sample_png_base64(sample_png_path: Path) -> str:
    """Return base64-encoded content of sample_medical_order.png.

    Generates the PNG if it does not exist (first run).
    """
    if not sample_png_path.exists():
        _generate_fixture_png(sample_png_path)
    with open(sample_png_path, "rb") as fh:
        return base64.b64encode(fh.read()).decode()


@pytest.fixture(scope="session")
def sample_png_sha256(sample_png_path: Path) -> str:
    """Return the SHA-256 hex digest of sample_medical_order.png."""
    if not sample_png_path.exists():
        _generate_fixture_png(sample_png_path)
    with open(sample_png_path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


@pytest.fixture
def valid_small_base64() -> str:
    """Return a valid base64 string that decodes to a tiny image (1 byte)."""
    return base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100).decode()


@pytest.fixture
def oversized_base64() -> str:
    """Return a base64 string that decodes to > 5 MB (for AC15 tests)."""
    # 6 MB of zeros
    return base64.b64encode(b"\x00" * (6 * 1024 * 1024)).decode()


def _generate_fixture_png(output_path: Path) -> None:
    """Generate sample_medical_order.png with Pillow.

    Contains:
    - Header "Pedido Médico"
    - Fake patient name (for PII masking tests)
    - Fake CPF 111.444.777-35 (for PII masking tests, AC4)
    - 3-5 exam names from the RAG catalog

    The file is generated deterministically — same content every run,
    so the SHA-256 hash is stable and can be used as a FIXTURES key.
    """
    try:
        from PIL import Image, ImageDraw  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            "Pillow is required to generate test fixtures. "
            "Install with: uv add --dev Pillow"
        ) from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Create a simple white image with medical order text
    img = Image.new("RGB", (600, 400), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Use default font (no external font needed)
    lines = [
        "PEDIDO MEDICO",
        "",
        "Paciente: Joao da Silva",
        "CPF: 111.444.777-35",
        "",
        "Exames Solicitados:",
        "1. Hemograma Completo",
        "2. Glicemia de Jejum",
        "3. Colesterol Total",
        "4. TSH",
        "5. Creatinina",
    ]

    y = 20
    for line in lines:
        draw.text((20, y), line, fill=(0, 0, 0))
        y += 30

    img.save(str(output_path), format="PNG")
