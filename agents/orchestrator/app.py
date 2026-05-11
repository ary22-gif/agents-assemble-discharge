"""Orchestrator Agent — A2A app entry point. Fully implemented in Phase 3."""

import os
from shared.app_factory import create_a2a_app, FHIR_EXTENSION_URI
from a2a.types import AgentSkill
from agents.orchestrator.agent import root_agent

_url = f"{os.getenv('A2A_BASE_URL', 'http://localhost')}:{os.getenv('ORCHESTRATOR_PORT', '8001')}"
_port = int(os.getenv("ORCHESTRATOR_PORT", "8001"))

a2a_app = create_a2a_app(
    agent=root_agent,
    name="discharge_coordinator",
    description=(
        "Discharge Coordinator — orchestrates MedRecon, CarePlan, and FollowUp agents "
        "in parallel via A2A to produce a complete, clinically-grounded discharge packet "
        "in under 60 seconds."
    ),
    url=_url,
    port=_port,
    fhir_extension_uri=FHIR_EXTENSION_URI,
    fhir_scopes=[
        {"name": "patient/Patient.rs", "required": True},
        {"name": "patient/MedicationRequest.rs", "required": True},
        {"name": "patient/MedicationStatement.rs", "required": True},
        {"name": "patient/Condition.rs", "required": True},
        {"name": "patient/CarePlan.rs", "required": True},
        {"name": "patient/Procedure.rs", "required": True},
        {"name": "patient/Appointment.rs", "required": True},
        {"name": "patient/ServiceRequest.rs", "required": True},
    ],
    skills=[
        AgentSkill(
            id="discharge_planning",
            name="Discharge Planning",
            description=(
                "Prepare a complete discharge packet: reconciled medications, "
                "patient-readable instructions, and follow-up scheduling — all "
                "grounded in the patient's FHIR record."
            ),
            tags=["discharge", "orchestration", "FHIR", "multi-agent"],
            examples=[
                "Prepare discharge for patient-001",
                "Generate discharge packet for Aragorn Strider",
            ],
        )
    ],
)
