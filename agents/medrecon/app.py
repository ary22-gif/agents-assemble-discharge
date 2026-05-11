"""MedRecon Agent — A2A app entry point. Fully implemented in Phase 3."""

import os
from shared.app_factory import create_a2a_app, FHIR_EXTENSION_URI
from a2a.types import AgentSkill
from agents.medrecon.agent import root_agent

_url = f"{os.getenv('A2A_BASE_URL', 'http://localhost')}:{os.getenv('MEDRECON_PORT', '8002')}"
_port = int(os.getenv("MEDRECON_PORT", "8002"))

a2a_app = create_a2a_app(
    agent=root_agent,
    name="discharge_medrecon_agent",
    description=(
        "Medication reconciliation agent. Retrieves MedicationRequest and "
        "MedicationStatement from FHIR, flags drug-drug interactions, and "
        "produces a reconciled medication list with RxNorm provenance."
    ),
    url=_url,
    port=_port,
    fhir_extension_uri=FHIR_EXTENSION_URI,
    fhir_scopes=[
        {"name": "patient/Patient.rs", "required": True},
        {"name": "patient/MedicationRequest.rs", "required": True},
        {"name": "patient/MedicationStatement.rs", "required": True},
    ],
    skills=[
        AgentSkill(
            id="medication_reconciliation",
            name="Medication Reconciliation",
            description="Reconcile inpatient and outpatient medications, flag interactions, produce discharge med list.",
            tags=["medication", "pharmacy", "discharge", "FHIR"],
            examples=["Reconcile medications for patient-001"],
        )
    ],
)
