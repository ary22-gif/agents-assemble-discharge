"""CarePlan Agent — patient-readable discharge instructions."""

import os
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from shared.fhir_hook import extract_fhir_context
from agents.careplan.tools import (
    get_patient_info,
    get_conditions,
    get_care_plans,
    get_procedures,
)
from agents.careplan.prompts import SYSTEM_PROMPT

_model = LiteLlm(model=os.getenv("CAREPLAN_MODEL", "gemini/gemini-2.5-flash"))

root_agent = Agent(
    name="discharge_careplan_agent",
    model=_model,
    description=(
        "Discharge instructions agent. Reads Condition, CarePlan, and Procedure "
        "resources from FHIR and generates patient-readable discharge instructions "
        "at ~6th-grade reading level, including red-flag symptoms."
    ),
    instruction=SYSTEM_PROMPT,
    tools=[
        get_patient_info,
        get_conditions,
        get_care_plans,
        get_procedures,
    ],
    before_model_callback=extract_fhir_context,
)
