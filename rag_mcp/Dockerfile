FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy rag_mcp package
COPY . /app/rag_mcp

# Install dependencies
WORKDIR /app/rag_mcp
RUN uv sync --no-dev

# SSE port (ADR-0001)
EXPOSE 8002

# Health check: HEAD /sse returns 200 or 405 (AC12)
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8002/sse')" || exit 1

CMD ["uv", "run", "python", "-m", "rag_mcp"]
