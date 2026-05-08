"""MedRecon Agent — medication reconciliation."""
import os
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from shared.fhir_hook import extract_fhir_context
from agents.medrecon.tools import (
    get_patient_info,
    get_medication_requests,
    get_medication_statements,
    check_drug_interactions,
)
from agents.medrecon.prompts import SYSTEM_PROMPT

_model = LiteLlm(model=os.getenv("MEDRECON_MODEL", "gemini/gemini-2.5-flash"))

root_agent = Agent(
    name="discharge_medrecon_agent",
    model=_model,
    description=(
        "Medication reconciliation agent. Retrieves MedicationRequest and "
        "MedicationStatement from FHIR, flags drug-drug interactions, and "
        "produces a reconciled medication list with RxNorm provenance."
    ),
    instruction=SYSTEM_PROMPT,
    tools=[
        get_patient_info,
        get_medication_requests,
        get_medication_statements,
        check_drug_interactions,
    ],
    before_model_callback=extract_fhir_context,
)
