FROM python:3.12-slim

# Install uv (ADR-0005)
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy scheduling_api package
# Build context = repo root
COPY scheduling_api /app/scheduling_api

# Install production deps via uv pip install --system (ADR-0005 — NOT uv sync)
RUN cd /app/scheduling_api && uv pip install --system --no-cache .

# HTTP port
EXPOSE 8000

# Explicit healthcheck fields — no implicit defaults (AC15, ADR-0008)
# interval ≤ 10s, timeout ≤ 5s, retries ≤ 10, start_period ≤ 60s per spec guardrails
HEALTHCHECK --interval=10s --timeout=3s --retries=5 --start-period=30s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)" || exit 1

CMD ["python", "-m", "scheduling_api"]
