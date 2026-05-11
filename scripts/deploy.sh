#!/usr/bin/env bash
# deploy.sh — Deploy all five Discharge Coordinator services to Google Cloud Run.
#
# Prerequisites:
#   1. gcloud CLI installed and authenticated:  gcloud auth login
#   2. Project set:  gcloud config set project YOUR_PROJECT_ID
#   3. APIs enabled:
#        gcloud services enable run.googleapis.com artifactregistry.googleapis.com
#   4. Artifact Registry repo created (run once):
#        gcloud artifacts repositories create discharge-agents \
#          --repository-format=docker --location=us-central1
#   5. GEMINI_API_KEY stored in Secret Manager:
#        echo -n "YOUR_KEY" | gcloud secrets create gemini-api-key --data-file=-
#   6. AGENT_API_KEY stored in Secret Manager:
#        echo -n "change-me-before-deploy" | gcloud secrets create agent-api-key --data-file=-
#
# Usage:
#   export GCP_PROJECT=your-gcp-project-id
#   export GCP_REGION=us-central1          # optional, default below
#   bash scripts/deploy.sh
#
# DEMO ONLY — SYNTHETIC DATA. NOT FOR CLINICAL USE.

set -euo pipefail

GCP_PROJECT="${GCP_PROJECT:?Set GCP_PROJECT env var to your GCP project ID}"
GCP_REGION="${GCP_REGION:-us-central1}"
IMAGE_REPO="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT}/discharge-agents/discharge"
IMAGE_TAG="${IMAGE_TAG:-latest}"
IMAGE="${IMAGE_REPO}:${IMAGE_TAG}"

echo "==> Building and pushing image: ${IMAGE}"
gcloud builds submit \
  --tag "${IMAGE}" \
  --project "${GCP_PROJECT}" \
  .

# Common flags for every Cloud Run service
COMMON=(
  --image "${IMAGE}"
  --region "${GCP_REGION}"
  --project "${GCP_PROJECT}"
  --platform managed
  --allow-unauthenticated
  --memory 1Gi
  --cpu 1
  --min-instances 0
  --max-instances 3
  --timeout 180
  --set-secrets "GEMINI_API_KEY=gemini-api-key:latest,AGENT_API_KEY=agent-api-key:latest"
  --set-env-vars "GOOGLE_GENAI_USE_VERTEXAI=FALSE,ADK_SUPPRESS_GEMINI_LITELLM_WARNINGS=true,LOG_LEVEL=INFO"
)

# ── 1. FHIR server ─────────────────────────────────────────────────────────────
echo ""
echo "==> Deploying fhir-server..."
gcloud run deploy discharge-fhir \
  "${COMMON[@]}" \
  --set-env-vars "AGENT_MODULE=fhir_server.main:app,PORT=8080,GOOGLE_GENAI_USE_VERTEXAI=FALSE,ADK_SUPPRESS_GEMINI_LITELLM_WARNINGS=true,LOG_LEVEL=INFO"

FHIR_URL=$(gcloud run services describe discharge-fhir \
  --region "${GCP_REGION}" --project "${GCP_PROJECT}" \
  --format "value(status.url)")
echo "  FHIR server URL: ${FHIR_URL}"

# ── 2. MedRecon sub-agent ──────────────────────────────────────────────────────
echo ""
echo "==> Deploying medrecon..."
gcloud run deploy discharge-medrecon \
  "${COMMON[@]}" \
  --set-env-vars "AGENT_MODULE=agents.medrecon.app:a2a_app,PORT=8080,FHIR_BASE_URL=${FHIR_URL}/fhir,GOOGLE_GENAI_USE_VERTEXAI=FALSE,ADK_SUPPRESS_GEMINI_LITELLM_WARNINGS=true,LOG_LEVEL=INFO"

MEDRECON_URL=$(gcloud run services describe discharge-medrecon \
  --region "${GCP_REGION}" --project "${GCP_PROJECT}" \
  --format "value(status.url)")
echo "  MedRecon URL: ${MEDRECON_URL}"

# ── 3. CarePlan sub-agent ──────────────────────────────────────────────────────
echo ""
echo "==> Deploying careplan..."
gcloud run deploy discharge-careplan \
  "${COMMON[@]}" \
  --set-env-vars "AGENT_MODULE=agents.careplan.app:a2a_app,PORT=8080,FHIR_BASE_URL=${FHIR_URL}/fhir,GOOGLE_GENAI_USE_VERTEXAI=FALSE,ADK_SUPPRESS_GEMINI_LITELLM_WARNINGS=true,LOG_LEVEL=INFO"

CAREPLAN_URL=$(gcloud run services describe discharge-careplan \
  --region "${GCP_REGION}" --project "${GCP_PROJECT}" \
  --format "value(status.url)")
echo "  CarePlan URL: ${CAREPLAN_URL}"

# ── 4. FollowUp sub-agent ──────────────────────────────────────────────────────
echo ""
echo "==> Deploying followup..."
gcloud run deploy discharge-followup \
  "${COMMON[@]}" \
  --set-env-vars "AGENT_MODULE=agents.followup.app:a2a_app,PORT=8080,FHIR_BASE_URL=${FHIR_URL}/fhir,GOOGLE_GENAI_USE_VERTEXAI=FALSE,ADK_SUPPRESS_GEMINI_LITELLM_WARNINGS=true,LOG_LEVEL=INFO"

FOLLOWUP_URL=$(gcloud run services describe discharge-followup \
  --region "${GCP_REGION}" --project "${GCP_PROJECT}" \
  --format "value(status.url)")
echo "  FollowUp URL: ${FOLLOWUP_URL}"

# ── 5. Orchestrator (entry point) ──────────────────────────────────────────────
echo ""
echo "==> Deploying orchestrator..."
gcloud run deploy discharge-orchestrator \
  "${COMMON[@]}" \
  --set-env-vars "AGENT_MODULE=agents.orchestrator.app:a2a_app,PORT=8080,FHIR_BASE_URL=${FHIR_URL}/fhir,MEDRECON_URL=${MEDRECON_URL},CAREPLAN_URL=${CAREPLAN_URL},FOLLOWUP_URL=${FOLLOWUP_URL},GOOGLE_GENAI_USE_VERTEXAI=FALSE,ADK_SUPPRESS_GEMINI_LITELLM_WARNINGS=true,LOG_LEVEL=INFO"

ORCHESTRATOR_URL=$(gcloud run services describe discharge-orchestrator \
  --region "${GCP_REGION}" --project "${GCP_PROJECT}" \
  --format "value(status.url)")

# ── Summary ────────────────────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo "  Deployment complete!"
echo "  FHIR server:  ${FHIR_URL}"
echo "  MedRecon:     ${MEDRECON_URL}"
echo "  CarePlan:     ${CAREPLAN_URL}"
echo "  FollowUp:     ${FOLLOWUP_URL}"
echo "  Orchestrator: ${ORCHESTRATOR_URL}  ← register this with Prompt Opinion"
echo ""
echo "  Agent card:   ${ORCHESTRATOR_URL}/.well-known/agent-card.json"
echo "============================================================"
echo ""
echo "Next: run scripts/register_agent.sh to generate the Prompt Opinion"
echo "registration JSON with the live orchestrator URL."
