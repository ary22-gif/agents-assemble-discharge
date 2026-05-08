"""Orchestrator tools — parallel A2A fan-out to sub-agents."""
import asyncio
import json
import logging
import os
import time

import httpx
from google.adk.tools import ToolContext

from shared.a2a_helpers import build_a2a_request
from shared.fhir_client import _get_fhir_context, fhir_get, http_error_result, connection_error_result

logger = logging.getLogger(__name__)

AGENT_API_KEY = os.getenv("AGENT_API_KEY", "")
BASE_URL      = os.getenv("A2A_BASE_URL", "http://localhost")

MEDRECON_URL  = os.getenv("MEDRECON_URL",  f"{BASE_URL}:{os.getenv('MEDRECON_PORT', '8002')}")
CAREPLAN_URL  = os.getenv("CAREPLAN_URL",  f"{BASE_URL}:{os.getenv('CAREPLAN_PORT', '8003')}")
FOLLOWUP_URL  = os.getenv("FOLLOWUP_URL",  f"{BASE_URL}:{os.getenv('FOLLOWUP_PORT', '8004')}")


def _extract_text_from_a2a_response(response: dict) -> str:
    """Pull text content from an A2A JSON-RPC result."""
    result = response.get("result", {})
    # ADK returns artifacts list
    artifacts = result.get("artifacts", [])
    if artifacts:
        parts = artifacts[0].get("parts", [])
        if parts:
            return parts[0].get("text", "")
    # Fallback: check status message
    status = result.get("status", {})
    message = status.get("message", {})
    parts = message.get("parts", [])
    if parts:
        return parts[0].get("text", "")
    return json.dumps(result)


def _parse_json_response(text: str) -> dict:
    """Extract JSON from agent text response (may be wrapped in markdown fences)."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text  = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"status": "parse_error", "raw": text[:500]}


async def _call_agent_async(
    agent_url: str,
    agent_name: str,
    fhir_url: str,
    fhir_token: str,
    patient_id: str,
    prompt: str,
    timeout: float = 120.0,
) -> tuple[dict, float]:
    payload = build_a2a_request(prompt, fhir_url, fhir_token, patient_id)
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": AGENT_API_KEY,
    }
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(agent_url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        elapsed_ms = (time.perf_counter() - start) * 1000
        text       = _extract_text_from_a2a_response(data)
        parsed     = _parse_json_response(text)
        logger.info("orchestrator_call agent=%s patient_id=%s duration_ms=%.1f status=%s",
                    agent_name, patient_id, elapsed_ms, parsed.get("status", "?"))
        return parsed, elapsed_ms
    except httpx.TimeoutException:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.error("orchestrator_timeout agent=%s", agent_name)
        return {"status": "error", "error_message": f"{agent_name} timed out after {timeout}s"}, elapsed_ms
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.error("orchestrator_error agent=%s err=%s", agent_name, e)
        return {"status": "error", "error_message": str(e)}, elapsed_ms


async def _prepare_packet_async(fhir_url: str, fhir_token: str, patient_id: str) -> dict:
    """Fan out to all three sub-agents in parallel, synthesize discharge packet."""
    import datetime

    # Fetch patient name for the packet header
    patient_name = patient_id  # fallback
    try:
        import httpx as _httpx
        p = fhir_get(fhir_url, fhir_token, f"Patient/{patient_id}")
        names    = p.get("name", [])
        official = next((n for n in names if n.get("use") == "official"), names[0] if names else {})
        patient_name = f"{' '.join(official.get('given', []))} {official.get('family', '')}".strip()
    except Exception:
        pass

    overall_start = time.perf_counter()

    medrecon_prompt = f"Perform medication reconciliation for patient {patient_id}. Use all available FHIR tools to retrieve medication data and check drug interactions."
    careplan_prompt = f"Generate discharge instructions for patient {patient_id}. Use all available FHIR tools to retrieve conditions, care plans, and procedures."
    followup_prompt = f"Identify all follow-up appointments and referrals for patient {patient_id}. Use all available FHIR tools to check scheduled appointments and pending service requests."

    results = await asyncio.gather(
        _call_agent_async(MEDRECON_URL,  "medrecon",  fhir_url, fhir_token, patient_id, medrecon_prompt),
        _call_agent_async(CAREPLAN_URL,  "careplan",  fhir_url, fhir_token, patient_id, careplan_prompt),
        _call_agent_async(FOLLOWUP_URL,  "followup",  fhir_url, fhir_token, patient_id, followup_prompt),
        return_exceptions=True,
    )

    total_ms = (time.perf_counter() - overall_start) * 1000

    def _unpack(r, name):
        if isinstance(r, Exception):
            return {"status": "error", "error_message": str(r)}, 0.0
        return r

    (med_data, med_ms), (care_data, care_ms), (fu_data, fu_ms) = [_unpack(r, n) for r, n in zip(results, ["medrecon","careplan","followup"])]

    # Merge provenance from all agents
    combined_provenance = (
        med_data.get("provenance", []) +
        care_data.get("provenance", []) +
        fu_data.get("provenance", [])
    )

    return {
        "status":            "success",
        "patient_id":        patient_id,
        "patient_name":      patient_name,
        "generated_at":      datetime.datetime.utcnow().isoformat() + "Z",
        "total_duration_ms": round(total_ms, 1),
        "medications":       med_data,
        "care_instructions": care_data,
        "follow_up":         fu_data,
        "agent_timings": [
            {"agent": "medrecon", "duration_ms": round(med_ms,  1), "status": med_data.get("status",  "?")},
            {"agent": "careplan", "duration_ms": round(care_ms, 1), "status": care_data.get("status", "?")},
            {"agent": "followup", "duration_ms": round(fu_ms,   1), "status": fu_data.get("status",  "?")},
        ],
        "provenance": combined_provenance,
        "disclaimer": "DEMO ONLY — SYNTHETIC DATA. NOT FOR CLINICAL USE.",
    }


def prepare_discharge_packet(tool_context: ToolContext) -> dict:
    """
    Orchestrate the full discharge packet for the patient in session context.

    Calls MedRecon, CarePlan, and FollowUp sub-agents in parallel via A2A,
    then synthesizes their outputs into a structured discharge packet.
    FHIR credentials are read from session state (injected by fhir_hook).

    No arguments required — patient identity and FHIR context come from
    the A2A message metadata provided by the caller.
    """
    ctx = _get_fhir_context(tool_context)
    if isinstance(ctx, dict):
        return ctx
    fhir_url, fhir_token, patient_id = ctx

    logger.info("orchestrator prepare_discharge_packet patient_id=%s", patient_id)
    logger.info("orchestrator sub-agents: medrecon=%s careplan=%s followup=%s",
                MEDRECON_URL, CAREPLAN_URL, FOLLOWUP_URL)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Inside an async context (e.g. uvicorn) — use run_coroutine_threadsafe
            import concurrent.futures
            future = asyncio.run_coroutine_threadsafe(
                _prepare_packet_async(fhir_url, fhir_token, patient_id), loop
            )
            return future.result(timeout=180)
        else:
            return loop.run_until_complete(
                _prepare_packet_async(fhir_url, fhir_token, patient_id)
            )
    except Exception as e:
        logger.exception("orchestrator error: %s", e)
        return {"status": "error", "error_message": str(e)}
