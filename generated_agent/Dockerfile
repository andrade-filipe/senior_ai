# Build context MUST be the repo root (not generated_agent/). See Block 0007 docker-compose.yml.
# docker build -f generated_agent/Dockerfile .
FROM python:3.12-slim

WORKDIR /app

# Copy security package (local dep — ADR-0003)
# Context = repo root, so paths are relative to that root.
COPY security /app/security

# Copy generated agent
COPY generated_agent /app/generated_agent

# Install all deps via uv (ADR-0005)
RUN pip install --no-cache-dir uv && \
    cd /app/generated_agent && \
    uv pip install --system .

# Google Gemini direct API — no Vertex AI (ADR-0005)
ENV GOOGLE_GENAI_USE_VERTEXAI=FALSE
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "generated_agent", "--image", "/data/order.png"]
