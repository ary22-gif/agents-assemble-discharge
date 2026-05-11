"""CarePlan Agent — A2A app entry point. Fully implemented in Phase 3."""

import os
from shared.app_factory import create_a2a_app, FHIR_EXTENSION_URI
from a2a.types import AgentSkill
from agents.careplan.agent import root_agent

_url = f"{os.getenv('A2A_BASE_URL', 'http://localhost')}:{os.getenv('CAREPLAN_PORT', '8003')}"
_port = int(os.getenv("CAREPLAN_PORT", "8003"))

a2a_app = create_a2a_app(
    agent=root_agent,
    name="discharge_careplan_agent",
    description=(
        "Discharge instructions agent. Reads Condition, CarePlan, and Procedure "
        "resources from FHIR and generates patient-readable discharge instructions "
        "at ~6th-grade reading level, including red-flag symptoms."
    ),
    url=_url,
    port=_port,
    fhir_extension_uri=FHIR_EXTENSION_URI,
    fhir_scopes=[
        {"name": "patient/Patient.rs", "required": True},
        {"name": "patient/Condition.rs", "required": True},
        {"name": "patient/CarePlan.rs", "required": True},
        {"name": "patient/Procedure.rs", "required": True},
    ],
    skills=[
        AgentSkill(
            id="discharge_instructions",
            name="Discharge Instructions",
            description="Generate patient-readable discharge instructions from FHIR Conditions, CarePlans, and Procedures.",
            tags=["careplan", "discharge", "patient-education", "FHIR"],
            examples=["Generate discharge instructions for patient-001"],
        )
    ],
)
