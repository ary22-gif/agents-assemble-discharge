"""Thin FHIR R4 client — authenticated GET helper used by all agent tools."""

import logging

import httpx
from google.adk.tools import ToolContext

logger = logging.getLogger(__name__)
_TIMEOUT = 15


def _get_fhir_context(tool_context: ToolContext):
    """Read FHIR credentials from session state (populated by fhir_hook)."""
    fhir_url = tool_context.state.get("fhir_url", "").rstrip("/")
    fhir_token = tool_context.state.get("fhir_token", "")
    patient_id = tool_context.state.get("patient_id", "")
    missing = [
        n
        for n, v in [
            ("fhir_url", fhir_url),
            ("fhir_token", fhir_token),
            ("patient_id", patient_id),
        ]
        if not v
    ]
    if missing:
        return {
            "status": "error",
            "error_message": f"FHIR context missing: {', '.join(missing)}. Include fhir-context in A2A metadata.",
        }
    return fhir_url, fhir_token, patient_id


def fhir_get(fhir_url: str, token: str, path: str, params: dict | None = None) -> dict:
    resp = httpx.get(
        f"{fhir_url}/{path}",
        params=params,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/fhir+json"},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def http_error_result(exc: httpx.HTTPStatusError) -> dict:
    return {
        "status": "error",
        "http_status": exc.response.status_code,
        "error_message": f"FHIR HTTP {exc.response.status_code}: {exc.response.text[:200]}",
    }


def connection_error_result(exc: Exception) -> dict:
    return {"status": "error", "error_message": f"FHIR unreachable: {exc}"}


def coding_display(codings: list) -> str:
    for c in codings:
        if c.get("display"):
            return c["display"]
    return "Unknown"


def extract_resource_id(resource: dict) -> str:
    """Return 'ResourceType/id' for provenance tracking."""
    rtype = resource.get("resourceType", "Resource")
    rid = resource.get("id", "unknown")
    return f"{rtype}/{rid}"
