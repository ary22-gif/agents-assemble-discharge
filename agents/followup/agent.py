"""FollowUp Agent — follow-up coordination."""
import os
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from shared.fhir_hook import extract_fhir_context
from agents.followup.tools import (
    get_patient_info,
    get_appointments,
    get_service_requests,
    get_conditions,
)
from agents.followup.prompts import SYSTEM_PROMPT

_model = LiteLlm(model=os.getenv("FOLLOWUP_MODEL", "gemini/gemini-2.5-flash"))

root_agent = Agent(
    name="discharge_followup_agent",
    model=_model,
    description=(
        "Follow-up coordination agent. Checks Appointment and ServiceRequest "
        "resources, identifies gaps against condition-specific windows, and "
        "recommends scheduling priorities."
    ),
    instruction=SYSTEM_PROMPT,
    tools=[
        get_patient_info,
        get_appointments,
        get_service_requests,
        get_conditions,
    ],
    before_model_callback=extract_fhir_context,
)
