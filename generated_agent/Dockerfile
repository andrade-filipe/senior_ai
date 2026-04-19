# Build context MUST be the repo root (not generated_agent/). See Block 0007 docker-compose.yml.
# docker build -f generated_agent/Dockerfile .
FROM python:3.12-slim

# Install uv (ADR-0005)
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy security package (local dep — ADR-0003)
# Context = repo root, so paths are relative to that root.
COPY security /app/security

# Copy generated agent
COPY generated_agent /app/generated_agent

# Install all deps via uv pip install --system (ADR-0005)
RUN cd /app/generated_agent && uv pip install --system --no-cache .

# Google Gemini direct API — no Vertex AI (ADR-0005)
ENV GOOGLE_GENAI_USE_VERTEXAI=FALSE
ENV PYTHONUNBUFFERED=1

# One-shot CLI — no HEALTHCHECK needed; compose uses service_started (ADR-0001)
# Caller passes --image <path> at runtime, e.g.:
#   docker compose run --rm generated-agent --image /fixtures/sample_medical_order.png
CMD ["python", "-m", "generated_agent"]
