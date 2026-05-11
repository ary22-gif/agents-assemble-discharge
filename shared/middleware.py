"""API key middleware — mirrors reference/shared/middleware.py.

Every request is blocked unless it carries a valid X-API-Key header.
The only public endpoints are /.well-known/agent-card.json and
/.well-known/agent.json, which callers need to discover the agent
before they can authenticate.

Also handles Prompt Opinion platform compatibility:
  - Normalises PascalCase JSON-RPC method names to spec names
  - Normalises proto-style role values (ROLE_USER → user)
  - Bridges FHIR metadata from message.metadata → params.metadata
  - Reshapes task responses to PO's a2a+json envelope format
"""

import json
import logging
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from shared.fhir_hook import extract_fhir_from_payload
from shared.logging_utils import redact_headers, safe_pretty_json, token_fingerprint

logger = logging.getLogger(__name__)

LOG_FULL_PAYLOAD = os.getenv("LOG_FULL_PAYLOAD", "true").lower() == "true"

AGENT_API_KEY = os.getenv("AGENT_API_KEY", "")

_PUBLIC_PATHS = {"/.well-known/agent-card.json", "/.well-known/agent.json"}

_METHOD_ALIASES: dict[str, str] = {
    "SendMessage": "message/send",
    "SendStreamingMessage": "message/send",
    "GetTask": "tasks/get",
    "CancelTask": "tasks/cancel",
    "TaskResubscribe": "tasks/resubscribe",
}

_ROLE_ALIASES: dict[str, str] = {
    "ROLE_USER": "user",
    "ROLE_AGENT": "agent",
}

_STATE_MAP: dict[str, str] = {
    "completed": "TASK_STATE_COMPLETED",
    "working": "TASK_STATE_WORKING",
    "submitted": "TASK_STATE_SUBMITTED",
    "input-required": "TASK_STATE_INPUT_REQUIRED",
    "failed": "TASK_STATE_FAILED",
    "canceled": "TASK_STATE_CANCELED",
}


def _fix_roles(node):
    if isinstance(node, dict):
        if "role" in node and node["role"] in _ROLE_ALIASES:
            node["role"] = _ROLE_ALIASES[node["role"]]
        for v in node.values():
            _fix_roles(v)
    elif isinstance(node, list):
        for item in node:
            _fix_roles(item)


class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        body_bytes = await request.body()
        body_text = body_bytes.decode("utf-8", errors="replace")
        parsed: dict = {}
        try:
            parsed = json.loads(body_text) if body_text else {}
        except json.JSONDecodeError:
            parsed = {}

        body_dirty = False

        # Normalise PascalCase method names (Prompt Opinion client compat)
        if isinstance(parsed, dict) and parsed.get("method") in _METHOD_ALIASES:
            original = parsed["method"]
            parsed["method"] = _METHOD_ALIASES[original]
            body_dirty = True
            logger.info("jsonrpc_method_rewritten original=%s rewritten=%s", original, parsed["method"])

        # Normalise proto-style role values
        if isinstance(parsed, dict):
            before = json.dumps(parsed, sort_keys=True)
            _fix_roles(parsed)
            if json.dumps(parsed, sort_keys=True) != before:
                body_dirty = True
                logger.info("jsonrpc_roles_normalised")

        if body_dirty:
            body_bytes = json.dumps(parsed, ensure_ascii=False).encode("utf-8")
            request._body = body_bytes  # type: ignore[attr-defined]

        # Log JSON-RPC method
        jsonrpc_method = parsed.get("method") if isinstance(parsed, dict) else None
        jsonrpc_id = parsed.get("id") if isinstance(parsed, dict) else None
        if jsonrpc_method:
            logger.info("jsonrpc_request id=%s method=%s path=%s", jsonrpc_id, jsonrpc_method, request.url.path)

        if LOG_FULL_PAYLOAD:
            logger.info(
                "incoming_http_request path=%s method=%s headers=%s\npayload=\n%s",
                request.url.path,
                request.method,
                safe_pretty_json(redact_headers(dict(request.headers))),
                safe_pretty_json(parsed) if parsed else body_text,
            )

        # Bridge FHIR metadata from message.metadata → params.metadata
        fhir_key, fhir_data = extract_fhir_from_payload(parsed)
        if isinstance(parsed, dict):
            params = parsed.get("params")
            if isinstance(params, dict):
                if fhir_key and fhir_data and not params.get("metadata"):
                    params["metadata"] = {fhir_key: fhir_data}
                    body_bytes = json.dumps(parsed, ensure_ascii=False).encode("utf-8")
                    request._body = body_bytes  # type: ignore[attr-defined]
                    logger.info("FHIR_METADATA_BRIDGED key=%s", fhir_key)
                if fhir_data:
                    logger.info("FHIR_URL_FOUND value=%s", fhir_data.get("fhirUrl", "[EMPTY]"))
                    logger.info("FHIR_TOKEN_FOUND fingerprint=%s", token_fingerprint(fhir_data.get("fhirToken", "")))
                    logger.info("FHIR_PATIENT_FOUND value=%s", fhir_data.get("patientId", "[EMPTY]"))
                else:
                    logger.info("FHIR_NOT_FOUND_IN_PAYLOAD")

        # Agent card endpoints are public
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        # Enforce API key auth
        if not AGENT_API_KEY:
            return await call_next(request)

        api_key = request.headers.get("X-API-Key", "")
        if not api_key:
            logger.warning("security_rejected_missing_api_key path=%s", request.url.path)
            return JSONResponse({"error": "Unauthorized", "detail": "X-API-Key header is required"}, status_code=401)

        if api_key != AGENT_API_KEY:
            logger.warning("security_rejected_invalid_api_key path=%s key_prefix=%s", request.url.path, api_key[:6])
            return JSONResponse({"error": "Forbidden", "detail": "Invalid API key"}, status_code=403)

        logger.info("security_authorized path=%s key_prefix=%s", request.url.path, api_key[:6])
        response = await call_next(request)

        # Reshape task responses to Prompt Opinion a2a+json envelope
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            resp_body = b""
            async for chunk in response.body_iterator:
                resp_body += chunk if isinstance(chunk, bytes) else chunk.encode()
            try:
                resp_parsed = json.loads(resp_body)
                result = resp_parsed.get("result") if isinstance(resp_parsed, dict) else None
                if isinstance(result, dict) and result.get("kind") == "task":
                    task: dict = {"id": result.get("id"), "contextId": result.get("contextId")}
                    status = result.get("status", {})
                    raw_state = status.get("state", "")
                    task["status"] = {"state": _STATE_MAP.get(raw_state, raw_state.upper())}
                    clean_artifacts = []
                    for artifact in result.get("artifacts", []):
                        clean_parts = [
                            {k: v for k, v in part.items() if k != "kind"}
                            for part in artifact.get("parts", [])
                        ]
                        clean_artifact = {k: v for k, v in artifact.items() if k != "parts"}
                        clean_artifact["parts"] = clean_parts
                        clean_artifacts.append(clean_artifact)
                    task["artifacts"] = clean_artifacts
                    resp_parsed["result"] = {"task": task}
                    logger.info("response_reshaped_to_po_a2a_json task_id=%s state=%s", task.get("id"), task["status"]["state"])
                resp_body = json.dumps(resp_parsed, ensure_ascii=False).encode("utf-8")
                if LOG_FULL_PAYLOAD:
                    logger.info(
                        "outgoing_response status=%s\nbody=\n%s",
                        response.status_code,
                        safe_pretty_json(resp_parsed),
                    )
            except Exception:
                logger.warning("outgoing_response_parse_failed body_raw=%s", resp_body[:500])

            from starlette.responses import Response as StarletteResponse

            headers = dict(response.headers)
            headers["content-length"] = str(len(resp_body))
            return StarletteResponse(
                content=resp_body,
                status_code=response.status_code,
                headers=headers,
                media_type=response.media_type,
            )

        return response
