# Discharge Coordinator — Project Status

> DEMO ONLY — SYNTHETIC DATA. NOT FOR CLINICAL USE.

## Phases

- [x] **Phase 0** — Project context
  - [x] CLAUDE.md created
  - [x] Reference repo cloned to ./reference/ (read-only)
  - [x] STATUS.md created
  - [ ] Initial commit + push to GitHub

- [ ] **Phase 1** — Scaffolding
  - [ ] Python 3.11+ / uv environment
  - [ ] Folder structure (agents/, fhir_server/, synthetic_data/, shared/, tests/, docs/, scripts/)
  - [ ] .env.example
  - [ ] Makefile
  - [ ] Pre-commit PHI guard hook
  - [ ] Commit + push

- [ ] **Phase 2** — Synthetic FHIR data + mock server
  - [ ] Patient 001 bundle (Post-CHF, 78yo)
  - [ ] Patient 002 bundle (Post-TKR, 62yo)
  - [ ] Patient 003 bundle (Post-pneumonia, 45yo)
  - [ ] FastAPI mock FHIR server
  - [ ] Smoke test all endpoints
  - [ ] Commit + push

- [ ] **Phase 3** — Build the four agents
  - [ ] MedRecon Agent (Gemini 2.5 Flash)
  - [ ] CarePlan Agent (Gemini 2.5 Flash)
  - [ ] FollowUp Agent (Gemini 2.5 Flash)
  - [ ] Orchestrator Agent (Gemini 2.5 Pro)
  - [ ] Guardrails (provenance, PHI check, reading-level)
  - [ ] Commit + push

- [ ] **Phase 4** — Local end-to-end + A2A test harness
  - [ ] /scripts/test_e2e.py
  - [ ] /scripts/simulate_promptopinion.py
  - [ ] Pytest suite (all green)
  - [ ] Commit + push

- [ ] **Phase 5** — Deployment
  - [ ] Dockerfiles + docker-compose.yml
  - [ ] Cloud Run deploy.sh (preferred)
  - [ ] Render.com fallback (render.yaml)
  - [ ] ngrok emergency fallback
  - [ ] Agent card JSON files for Prompt Opinion registration
  - [ ] /docs/PLATFORM_INTEGRATION.md
  - [ ] Commit + push

- [ ] **Phase 6** — Submission assets
  - [ ] /docs/architecture.mmd (Mermaid diagram)
  - [ ] /docs/DEMO_SCRIPT.md
  - [ ] /docs/DEVPOST_SUBMISSION.md
  - [ ] README.md polish
  - [ ] /docs/SUBMISSION_CHECKLIST.md
  - [ ] Commit + push

- [ ] **Phase 7** — Pre-submission verification
  - [ ] All checklist items green
  - [ ] Submitted by 9pm ET May 11 2026

## Key Reference Patterns (from ./reference/)

- `shared/app_factory.py` → `create_a2a_app()` — builds A2A ASGI app with AgentCardV1
- `shared/fhir_hook.py` → `extract_fhir_context` — ADK before_model_callback for FHIR metadata
- `shared/tools/fhir.py` → FHIR tool pattern (reads from `tool_context.state`)
- `AgentExtensionV1` / `AgentCardV1` — patches for A2A v1 spec compliance
- FHIR context key: `"fhir-context"` substring match in metadata keys
