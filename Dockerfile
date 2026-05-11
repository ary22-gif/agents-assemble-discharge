# Discharge Coordinator — single image for all five services.
#
# AGENT_MODULE env var selects which ASGI app to run at startup.
# Cloud Run sets PORT to 8080 automatically; override for local Docker testing.
#
# Valid AGENT_MODULE values:
#   fhir_server.main:app                (mock FHIR R4 server)
#   agents.medrecon.app:a2a_app         (medication reconciliation agent)
#   agents.careplan.app:a2a_app         (care-plan / discharge instructions agent)
#   agents.followup.app:a2a_app         (follow-up coordination agent)
#   agents.orchestrator.app:a2a_app     (orchestrator — entry point for Prompt Opinion)
#
# Local build + smoke test:
#   docker build -t discharge .
#   docker run --rm -p 8080:8080 \
#     -e AGENT_MODULE=fhir_server.main:app \
#     discharge
#
# Then run all five: docker compose up --build

FROM python:3.11-slim

WORKDIR /app

# Layer 1 — dependencies (cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Layer 2 — application code
COPY agents/    agents/
COPY fhir_server/ fhir_server/
COPY shared/    shared/
COPY synthetic_data/ synthetic_data/

# Default env (overridden per-service in Compose / Cloud Run)
ENV PORT=8080
ENV AGENT_MODULE=agents.orchestrator.app:a2a_app

# exec replaces the shell so uvicorn is PID 1 and receives SIGTERM cleanly
CMD ["sh", "-c", "exec uvicorn ${AGENT_MODULE} --host 0.0.0.0 --port ${PORT}"]
