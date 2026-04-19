FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy the security package first (dependency)
COPY ../security /app/security

# Copy ocr_mcp package
COPY . /app/ocr_mcp

# Install dependencies
WORKDIR /app/ocr_mcp
RUN uv sync --no-dev

# SSE port (ADR-0001)
EXPOSE 8001

# Health check: HEAD /sse returns 200 or 405 (AC12)
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/sse')" || exit 1

CMD ["uv", "run", "python", "-m", "ocr_mcp"]
