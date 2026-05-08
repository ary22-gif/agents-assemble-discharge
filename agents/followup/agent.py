"""FollowUp Agent definition — stub, implemented in Phase 3."""
import os
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from shared.fhir_hook import extract_fhir_context

_model = LiteLlm(model=os.getenv("FOLLOWUP_MODEL", "gemini/gemini-2.5-flash"))

root_agent = Agent(
    name="discharge_followup_agent",
    model=_model,
    description="Follow-up coordination agent — stub.",
    instruction="Stub — implemented in Phase 3.",
    tools=[],
    before_model_callback=extract_fhir_context,
)
