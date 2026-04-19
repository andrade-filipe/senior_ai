FROM python:3.12-slim

# Install uv (ADR-0005)
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy rag_mcp package
# Build context = repo root
COPY rag_mcp /app/rag_mcp

# Install production deps via uv pip install --system (ADR-0005 — NOT uv sync)
RUN cd /app/rag_mcp && uv pip install --system --no-cache .

# SSE port (ADR-0001)
EXPOSE 8002

# Explicit healthcheck fields — no implicit defaults (AC15, ADR-0008)
HEALTHCHECK --interval=10s --timeout=5s --retries=3 --start-period=15s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8002/sse', timeout=2)" || exit 1

CMD ["python", "-m", "rag_mcp"]
