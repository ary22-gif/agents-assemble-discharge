# Discharge Coordinator — Claude Code Context

## Project Overview
A2A-enabled multi-agent discharge planning system for the Agents Assemble: Healthcare AI Endgame hackathon.
- **Prize**: $25K pool, $7.5K grand prize
- **Deadline**: Monday May 11 2026, 11pm ET (submit by 9pm ET)
- **Platform**: Prompt Opinion (app.promptopinion.ai)

## Elevator Pitch
A team of four FHIR-aware AI agents that collaborate via Google's A2A protocol to prepare a complete, clinically-grounded discharge packet in under 60 seconds — reducing the 45-min/patient burden on hospitalists and tackling the #1 driver of 30-day readmissions.

## Architecture
- **Orchestrator Agent** (Gemini 2.5 Pro) — entry point. Receives "prepare discharge for patient {id}", delegates to three sub-agents in parallel via A2A, synthesizes their outputs into a structured discharge packet (JSON + patient-readable markdown).
- **MedRecon Agent** (Gemini 2.5 Flash) — pulls MedicationRequest + MedicationStatement from FHIR, identifies polypharmacy risk, flags potential drug-drug interactions using a synthetic interaction table, generates a reconciled medication list.
- **CarePlan Agent** (Gemini 2.5 Flash) — pulls Condition + CarePlan + Procedure resources, generates patient-readable discharge instructions targeted at ~6th-grade reading level, includes red-flag symptoms that warrant returning to the ER.
- **FollowUp Agent** (Gemini 2.5 Flash) — pulls Appointment + ServiceRequest, identifies missing follow-up appointments based on conditions, suggests scheduling within clinically-appropriate windows.

## A2A Compliance Requirements
- All four agents must be A2A v1 spec compliant (https://a2a-protocol.org/latest/announcing-1.0/)
- Properly-formed agent card declaring skills and the SHARP FHIR-context extension at URI: `https://app.promptopinion.ai/schemas/a2a/v1/fhir-context`
- Read fhirUrl, fhirToken, patientId from message metadata at that extension URI
- Refuse to invent any clinical data not in the FHIR response — every claim must be traceable to a FHIR resource ID

## SMART Scopes per Agent
- MedRecon: `patient/MedicationRequest.rs patient/MedicationStatement.rs patient/Patient.rs`
- CarePlan: `patient/Condition.rs patient/CarePlan.rs patient/Procedure.rs patient/Patient.rs`
- FollowUp: `patient/Appointment.rs patient/ServiceRequest.rs patient/Patient.rs`

## Non-Negotiable Constraints
- Synthetic data only. Banner: "DEMO ONLY — SYNTHETIC DATA. NOT FOR CLINICAL USE."
- Real RxNorm codes and ICD-10 codes in synthetic FHIR bundles
- No real PHI. Fictional patient names (e.g., "Aragorn Strider", "Padmé Amidala")
- Reference repo: ./reference/po-adk-python (read-only, never modify)

## Judging Criteria
1. **AI Factor**: synthesis across multiple FHIR resources — rule-based software can't do this well
2. **Potential Impact**: hospitalists spend ~45 min/patient on discharge prep; 30-day readmissions cost US ~$26B/year; Hospital Readmissions Reduction Program penalizes hospitals
3. **Feasibility**: SMART-on-FHIR scopes, no PHI, audit logging, structured outputs, deterministic provenance

## Synthetic Patients
- **Patient 001**: Post-CHF, 78yo, furosemide + lisinopril + carvedilol, T2DM comorbidity, missing 7-day cardiology follow-up
- **Patient 002**: Post-total knee replacement, 62yo, apixaban + acetaminophen-oxycodone, missing PT referral
- **Patient 003**: Post-pneumonia (CAP), 45yo, azithromycin + albuterol, asthma comorbidity, missing 2-week PCP follow-up

## Phases
- Phase 0: Project context (CLAUDE.md, clone reference, STATUS.md, initial commit)
- Phase 1: Scaffolding (folder structure, uv, Makefile, pre-commit hook)
- Phase 2: Synthetic FHIR data + mock server
- Phase 3: Build the four agents
- Phase 4: Local end-to-end + A2A test harness
- Phase 5: Deployment
- Phase 6: Submission assets
- Phase 7: Pre-submission verification

## Key Links
- A2A Spec: https://a2a-protocol.org/latest/announcing-1.0/
- FHIR Context Extension: https://app.promptopinion.ai/schemas/a2a/v1/fhir-context
- Prompt Opinion FHIR Context Docs: https://docs.promptopinion.ai/fhir-context/a2a-fhir-context
- Reference repo: ./reference/po-adk-python

## Safety Rules
- Pre-commit hook blocks SSN/MRN regex patterns
- Output validator: every clinical claim must reference a FHIR resource ID in input
- Output validator: no PHI patterns in output
- Reading-level scorer for CarePlan output (target Flesch-Kincaid grade ~6)
