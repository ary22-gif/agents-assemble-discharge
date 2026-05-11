"""FollowUp Agent — A2A app entry point. Fully implemented in Phase 3."""

import os
from shared.app_factory import create_a2a_app, FHIR_EXTENSION_URI
from a2a.types import AgentSkill
from agents.followup.agent import root_agent

_url = f"{os.getenv('A2A_BASE_URL', 'http://localhost')}:{os.getenv('FOLLOWUP_PORT', '8004')}"
_port = int(os.getenv("FOLLOWUP_PORT", "8004"))

a2a_app = create_a2a_app(
    agent=root_agent,
    name="discharge_followup_agent",
    description=(
        "Follow-up coordination agent. Checks Appointment and ServiceRequest "
        "resources, identifies gaps against condition-specific windows, and "
        "recommends scheduling priorities."
    ),
    url=_url,
    port=_port,
    fhir_extension_uri=FHIR_EXTENSION_URI,
    fhir_scopes=[
        {"name": "patient/Patient.rs", "required": True},
        {"name": "patient/Appointment.rs", "required": True},
        {"name": "patient/ServiceRequest.rs", "required": True},
        {"name": "patient/Condition.rs", "required": True},
    ],
    skills=[
        AgentSkill(
            id="followup_coordination",
            name="Follow-Up Coordination",
            description="Identify missing follow-up appointments and suggest clinically-appropriate scheduling windows.",
            tags=["followup", "scheduling", "discharge", "FHIR"],
            examples=["Check follow-up appointments for patient-001"],
        )
    ],
)
