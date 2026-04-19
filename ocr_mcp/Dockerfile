FROM python:3.12-slim

# Install uv (ADR-0005)
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy security package (local dep — ADR-0003)
# Build context = repo root (ocr_mcp depends on security/)
COPY security /app/security

# Copy ocr_mcp package
COPY ocr_mcp /app/ocr_mcp

# Install production deps via uv pip install --system (ADR-0005 — NOT uv sync)
RUN cd /app/ocr_mcp && uv pip install --system --no-cache .

# SSE port (ADR-0001)
EXPOSE 8001

# Explicit healthcheck fields — no implicit defaults (AC15, ADR-0008)
HEALTHCHECK --interval=10s --timeout=5s --retries=3 --start-period=15s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/sse', timeout=2)" || exit 1

CMD ["python", "-m", "ocr_mcp"]
