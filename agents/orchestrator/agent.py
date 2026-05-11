"""Orchestrator Agent — parallel A2A discharge packet coordinator."""

import os
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from shared.fhir_hook import extract_fhir_context
from agents.orchestrator.tools import prepare_discharge_packet
from agents.orchestrator.prompts import SYSTEM_PROMPT

_model = LiteLlm(model=os.getenv("ORCHESTRATOR_MODEL", "gemini/gemini-2.5-pro"))

root_agent = Agent(
    name="discharge_coordinator",
    model=_model,
    description=(
        "Discharge Coordinator — orchestrates MedRecon, CarePlan, and FollowUp agents "
        "in parallel via A2A to produce a complete, clinically-grounded discharge packet "
        "in under 60 seconds."
    ),
    instruction=SYSTEM_PROMPT,
    tools=[prepare_discharge_packet],
    before_model_callback=extract_fhir_context,
)
