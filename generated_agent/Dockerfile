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

# spaCy model — PII Layer 2 (before_model_callback) runs in-process inside
# the agent container. Runtime download would trip the 5 s guard timeout.
# ARG lets the operator swap the model via build.args in docker-compose.yml
# without modifying application code (ADR-0009).
ARG PII_SPACY_MODEL_PT=pt_core_news_lg
RUN python -m spacy download $PII_SPACY_MODEL_PT

# Google Gemini direct API — no Vertex AI (ADR-0005)
ENV GOOGLE_GENAI_USE_VERTEXAI=FALSE
ENV PYTHONUNBUFFERED=1

# One-shot CLI — no HEALTHCHECK needed; compose uses service_started (ADR-0001)
# ENTRYPOINT (not CMD) so `docker compose run ... --image <path>` appends to
# the module invocation instead of replacing it. With CMD the runtime args
# would shadow ["python","-m","generated_agent"] and exec `--image` directly.
ENTRYPOINT ["python", "-m", "generated_agent"]
