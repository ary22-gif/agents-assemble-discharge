# Prompt Opinion Platform Integration Guide

**DEMO ONLY — SYNTHETIC DATA. NOT FOR CLINICAL USE.**

## Overview

The Discharge Coordinator exposes a single entry point — the **Orchestrator** agent — via the A2A v1 JSON-RPC protocol. Prompt Opinion calls the orchestrator with a `message/send` request that carries FHIR credentials in the message metadata. The orchestrator fans out to three sub-agents (MedRecon, CarePlan, FollowUp) in parallel and synthesizes a complete discharge packet.

---

## Prerequisites

| Requirement | Details |
|---|---|
| Python 3.11+ | Required for local dev |
| Docker Desktop | Required for Compose deployment |
| `gcloud` CLI | Required for Cloud Run deployment |
| `GEMINI_API_KEY` | Google AI Studio — https://ai.google.dev |
| `AGENT_API_KEY` | Any random string; set the same value in PO and your deployment |

---

## Deployment Options

### Option A — Docker Compose (local / ngrok demo)

```bash
cp .env.example .env
# Edit .env: set GEMINI_API_KEY and AGENT_API_KEY
docker compose up --build
```

Services start on ports 8000–8004. For a public URL (needed to register with PO):

```bash
ngrok http 8001   # expose the orchestrator
```

Copy the `https://*.ngrok-free.app` URL as your orchestrator URL.

---

### Option B — Google Cloud Run (recommended for submission)

```bash
export GCP_PROJECT=your-gcp-project-id

# One-time setup
gcloud services enable run.googleapis.com artifactregistry.googleapis.com
gcloud artifacts repositories create discharge-agents \
  --repository-format=docker --location=us-central1
echo -n "$GEMINI_API_KEY" | gcloud secrets create gemini-api-key --data-file=-
echo -n "$AGENT_API_KEY"  | gcloud secrets create agent-api-key  --data-file=-

# Deploy all five services (~5 min)
bash scripts/deploy.sh
```

The script prints the final orchestrator URL.

---

### Option C — Render.com (zero-gcloud fallback)

1. Push repo to GitHub.
2. Go to `dashboard.render.com` → **New** → **Blueprint** → select this repo.
3. Set environment group `discharge-secrets`:
   - `GEMINI_API_KEY` = your key
   - `AGENT_API_KEY` = your shared secret
4. After deploy, note the sub-agent URLs and set them on the orchestrator service:
   - `MEDRECON_URL`, `CAREPLAN_URL`, `FOLLOWUP_URL`

---

## Registering with Prompt Opinion

Once the orchestrator is publicly accessible:

```bash
export ORCHESTRATOR_URL=https://discharge-orchestrator-xxx.a.run.app
bash scripts/register_agent.sh
# Writes registration/orchestrator-card.json
```

Then in the Prompt Opinion workspace:

1. **Agents → Add Agent**
2. Enter **Agent URL**: `${ORCHESTRATOR_URL}`
3. PO fetches `/.well-known/agent-card.json` automatically.
4. Add the **API Key secret** matching your `AGENT_API_KEY`.
5. Set the **FHIR context extension** to `https://app.promptopinion.ai/schemas/a2a/v1/fhir-context`.

---

## A2A Request Format

Prompt Opinion sends requests in this format:

```json
{
  "jsonrpc": "2.0",
  "id": "task-uuid",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "parts": [{"kind": "text", "text": "Prepare discharge for patient patient-001"}],
      "metadata": {
        "https://app.promptopinion.ai/schemas/a2a/v1/fhir-context": {
          "fhirUrl": "https://your-fhir-server/fhir",
          "fhirToken": "Bearer <smart-on-fhir-token>",
          "patientId": "patient-001"
        }
      }
    }
  }
}
```

The middleware automatically normalises PascalCase method names (`SendMessage` → `message/send`) for backwards compatibility with older PO clients.

---

## Response Format

The orchestrator returns a structured discharge packet:

```json
{
  "status": "success",
  "patient_id": "patient-001",
  "patient_name": "Aragorn Strider",
  "generated_at": "2026-05-10T18:00:00Z",
  "total_duration_ms": 12500,
  "medications": { ... },
  "care_instructions": { ... },
  "follow_up": { ... },
  "agent_timings": [ ... ],
  "provenance": [ ... ],
  "disclaimer": "DEMO ONLY — SYNTHETIC DATA. NOT FOR CLINICAL USE."
}
```

---

## Smoke Test After Deployment

```bash
# 1. Check agent card
curl https://your-orchestrator-url/.well-known/agent-card.json | python3 -m json.tool

# 2. Send a test message (patient-001 = Aragorn Strider, CHF)
curl -X POST https://your-orchestrator-url \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $AGENT_API_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "id": "smoke-test-1",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "Prepare discharge for patient patient-001"}],
        "metadata": {
          "https://app.promptopinion.ai/schemas/a2a/v1/fhir-context": {
            "fhirUrl": "https://your-fhir-url/fhir",
            "fhirToken": "demo-token",
            "patientId": "patient-001"
          }
        }
      }
    }
  }'
```

Expected: JSON-RPC response with `result.artifacts[0].parts[0].text` containing a discharge packet JSON with `status: "success"`.

---

## Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Google AI Studio API key |
| `AGENT_API_KEY` | Yes | Shared secret for X-API-Key header |
| `MEDRECON_URL` | Orchestrator only | MedRecon service URL |
| `CAREPLAN_URL` | Orchestrator only | CarePlan service URL |
| `FOLLOWUP_URL` | Orchestrator only | FollowUp service URL |
| `FHIR_BASE_URL` | Optional | Override FHIR server URL |
| `ORCHESTRATOR_MODEL` | Optional | Default: `gemini/gemini-2.5-pro` |
| `MEDRECON_MODEL` | Optional | Default: `gemini/gemini-2.5-flash` |
| `CAREPLAN_MODEL` | Optional | Default: `gemini/gemini-2.5-flash` |
| `FOLLOWUP_MODEL` | Optional | Default: `gemini/gemini-2.5-flash` |
| `LOG_LEVEL` | Optional | Default: `INFO` |
| `ADK_SUPPRESS_GEMINI_LITELLM_WARNINGS` | Optional | Set `true` to silence advisory warnings |

---

## SMART Scopes Declared

| Agent | Scopes |
|---|---|
| MedRecon | `patient/MedicationRequest.rs patient/MedicationStatement.rs patient/Patient.rs` |
| CarePlan | `patient/Condition.rs patient/CarePlan.rs patient/Procedure.rs patient/Patient.rs` |
| FollowUp | `patient/Appointment.rs patient/ServiceRequest.rs patient/Patient.rs` |

---

## Synthetic Patients

| ID | Name | Condition | Key Care Gap |
|---|---|---|---|
| `patient-001` | Aragorn Strider | CHF + T2DM | Missing 7-day cardiology follow-up |
| `patient-002` | Padmé Amidala | Post-TKR | Apixaban+ibuprofen MAJOR interaction |
| `patient-003` | Bilbo Baggins | CAP + asthma | Missing 2-week PCP follow-up |
