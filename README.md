# Agents Assemble — Discharge Coordinator

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![Google ADK](https://img.shields.io/badge/Google%20ADK-1.33-4285F4?logo=google&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini-2.5%20Pro%20%2F%20Flash-4285F4?logo=google&logoColor=white)
![A2A](https://img.shields.io/badge/A2A-v1%20Protocol-34A853)
![FHIR](https://img.shields.io/badge/FHIR-R4%20SMART--on--FHIR-E40046)
![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688?logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)

> **DEMO ONLY — SYNTHETIC DATA. NOT FOR CLINICAL USE.**

A team of four FHIR-aware AI agents that collaborate via Google's A2A protocol to produce a complete, clinically-grounded discharge packet in under 60 seconds — targeting the 45 min/patient burden on hospitalists and the $26B/year cost of 30-day readmissions in the US.

Built for the **Agents Assemble: Healthcare AI Endgame** hackathon ($25K prize pool).

---

## Project Overview

Hospital discharge is a high-stakes coordination problem. A hospitalist must reconcile medications, write patient-readable instructions at the right literacy level, identify missing follow-up appointments — all under time pressure, for every patient. Errors here drive 30-day readmissions, which cost the US healthcare system ~$26B/year and trigger HRRP penalties.

This system replaces that manual workflow with four specialized AI agents that fan out in parallel, each pulling clinically-relevant FHIR resources, and reconvene into a structured discharge packet. Every clinical claim is traceable to a FHIR resource ID. No clinical data is invented.

---

## Architecture

```
User / EHR Platform
        │
        ▼ A2A v1 (FHIR context in message metadata)
┌──────────────────────────────────┐
│   Orchestrator Agent             │  Gemini 2.5 Pro
│   discharge_coordinator         │  Delegates to sub-agents in parallel,
│                                  │  synthesizes discharge packet (JSON + markdown)
└──────┬──────────┬────────────────┘
       │          │          │
       ▼          ▼          ▼
┌──────────┐ ┌──────────┐ ┌──────────────┐
│ MedRecon │ │ CarePlan │ │   FollowUp   │
│  Agent   │ │  Agent   │ │    Agent     │
│Flash 2.5 │ │Flash 2.5 │ │  Flash 2.5  │
└──────────┘ └──────────┘ └──────────────┘
     │              │              │
     ▼              ▼              ▼
  FHIR Server (FastAPI mock — synthetic data only)
```

### Agents

| Agent | Model | FHIR Resources | Responsibility |
|-------|-------|----------------|---------------|
| **Orchestrator** | Gemini 2.5 Pro | — | Delegates to sub-agents in parallel, synthesizes final packet |
| **MedRecon** | Gemini 2.5 Flash | MedicationRequest, MedicationStatement | Medication reconciliation, DDI flags, RxNorm provenance |
| **CarePlan** | Gemini 2.5 Flash | Condition, CarePlan, Procedure | Patient-readable instructions at ~6th-grade reading level, red-flag symptoms |
| **FollowUp** | Gemini 2.5 Flash | Appointment, ServiceRequest | Gap analysis, scheduling recommendations within clinical windows |

---

## Synthetic Patients

| Patient | Condition | Key Complexity |
|---------|-----------|---------------|
| Patient 001 (Aragorn Strider, 78M) | Post-CHF | Furosemide + lisinopril + carvedilol, T2DM comorbidity, missing 7-day cardiology follow-up |
| Patient 002 (Padmé Amidala, 62F) | Post-total knee replacement | Apixaban + acetaminophen/oxycodone polypharmacy, missing PT referral |
| Patient 003 (Bilbo Baggins, 45M) | Post-pneumonia (CAP) | Azithromycin + albuterol, asthma comorbidity, missing 2-week PCP follow-up |

---

## Key Features

- **A2A v1 spec compliant** — all four agents expose properly-formed agent cards with the Prompt Opinion FHIR context extension (`https://app.promptopinion.ai/schemas/a2a/v1/fhir-context`)
- **FHIR provenance** — every clinical claim references the originating FHIR resource ID; refuses to invent data
- **PHI guardrails** — pre-commit hook blocks SSN/MRN regex patterns; output validator checks for PHI before returning
- **Reading-level scoring** — CarePlan output scored against Flesch-Kincaid grade 6 target using `textstat`
- **Parallel fan-out** — orchestrator dispatches MedRecon, CarePlan, and FollowUp concurrently; 60-second target
- **Idempotent FHIR server** — FastAPI mock serves synthetic FHIR R4 bundles with real RxNorm and ICD-10 codes

---

## How to Run

### Prerequisites

```bash
# Python 3.11+ with uv
pip install uv
uv sync

# Copy environment variables
cp .env.example .env
# Edit .env: add GOOGLE_API_KEY (Gemini) and other required vars
```

### Start services

```bash
# Full stack via Docker Compose
docker compose up --build

# Or individual agents (for local dev)
make run-fhir       # Mock FHIR server on :8080
make run-medrecon   # MedRecon agent on :8081
make run-careplan   # CarePlan agent on :8082
make run-followup   # FollowUp agent on :8083
make run-orchestrator  # Orchestrator on :8084
```

### End-to-end test

```bash
# Simulate Prompt Opinion platform sending a discharge request
python scripts/simulate_promptopinion.py --patient-id patient-001

# Full pytest suite
pytest tests/ -v
```

### Register agents on Prompt Opinion

```bash
bash scripts/register_agent.sh
```

---

## Repository Structure

```
agents-assemble-discharge/
├── agents/
│   ├── orchestrator/    # Gemini 2.5 Pro — fan-out coordinator
│   ├── medrecon/        # Gemini 2.5 Flash — medication reconciliation
│   ├── careplan/        # Gemini 2.5 Flash — discharge instructions
│   └── followup/        # Gemini 2.5 Flash — follow-up gap analysis
├── fhir_server/         # FastAPI mock FHIR R4 server
├── shared/              # A2A helpers, FHIR client, guardrails, schemas
├── synthetic_data/      # Patient 001–003 FHIR bundles (synthetic only)
├── scripts/             # E2E test, Prompt Opinion simulation, PHI guard
├── tests/               # Pytest suite per agent + integration
├── docs/                # Platform integration guide
└── docker-compose.yml   # Full stack orchestration
```

---

## Tech Stack

| Tool | Purpose |
|------|---------|
| Google ADK 1.33 | Agent framework (before_model_callback, tool dispatch) |
| Gemini 2.5 Pro / Flash | LLM backbone for orchestrator and sub-agents |
| A2A SDK 0.3.26 | Agent-to-agent protocol (v1 spec) |
| FastAPI 0.136 | FHIR mock server and agent HTTP endpoints |
| LiteLLM 1.83.7 | Unified LLM routing |
| Pydantic v2 | Schema validation for FHIR resources and discharge packet |
| textstat | Flesch-Kincaid reading-level scoring |
| uv | Fast Python dependency management |
| Docker Compose | Multi-service orchestration |
| Render / Cloud Run | Deployment targets |

---

## Clinical Impact

| Metric | Value |
|--------|-------|
| Current hospitalist discharge prep time | ~45 min/patient (manual) |
| Target with this system | <60 seconds |
| US 30-day readmission cost | ~$26B/year |
| HRRP penalty trigger | Readmission within 30 days of discharge |

---

## Author

**Ayush Yadav** | M.S. AI @ NJIT | [ary22@njit.edu](mailto:ary22@njit.edu)
