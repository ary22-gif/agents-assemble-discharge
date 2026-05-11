"""A2A JSON-RPC helpers for the Orchestrator's outbound calls to sub-agents."""

import asyncio
import logging
import time
import uuid

import httpx

logger = logging.getLogger(__name__)

FHIR_EXTENSION_URI = "https://app.promptopinion.ai/schemas/a2a/v1/fhir-context"


def build_a2a_request(
    text: str,
    fhir_url: str,
    fhir_token: str,
    patient_id: str,
    task_id: str | None = None,
) -> dict:
    """Build an A2A v1 JSON-RPC SendMessage request with FHIR metadata."""
    return {
        "jsonrpc": "2.0",
        "id": task_id or str(uuid.uuid4()),
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": text}],
                "metadata": {
                    FHIR_EXTENSION_URI: {
                        "fhirUrl": fhir_url,
                        "fhirToken": fhir_token,
                        "patientId": patient_id,
                    }
                },
            }
        },
    }


async def call_agent(
    agent_url: str,
    text: str,
    fhir_url: str,
    fhir_token: str,
    patient_id: str,
    api_key: str,
    timeout: float = 60.0,
) -> tuple[dict, float]:
    """Send an A2A message to a sub-agent and return the parsed response."""
    payload = build_a2a_request(text, fhir_url, fhir_token, patient_id)
    headers = {"Content-Type": "application/json", "X-API-Key": api_key}
    start = time.perf_counter()

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(agent_url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "a2a_call url=%s patient_id=%s duration_ms=%.1f",
        agent_url,
        patient_id,
        elapsed_ms,
    )
    return data, elapsed_ms


async def call_agents_parallel(calls: list[dict]) -> list:
    """
    Fire multiple A2A agent calls in parallel via asyncio.gather.

    Each element of `calls` is a dict with keys:
      agent_url, text, fhir_url, fhir_token, patient_id, api_key
    Returns list of (result, elapsed_ms) tuples in the same order.
    """
    tasks = [
        call_agent(
            agent_url=c["agent_url"],
            text=c["text"],
            fhir_url=c["fhir_url"],
            fhir_token=c["fhir_token"],
            patient_id=c["patient_id"],
            api_key=c["api_key"],
        )
        for c in calls
    ]
    return await asyncio.gather(*tasks, return_exceptions=True)  # type: ignore[return-value]
