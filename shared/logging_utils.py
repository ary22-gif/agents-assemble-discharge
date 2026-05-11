"""Shared logging helpers."""

import json
import logging
import os
from typing import Any


def configure_logging():
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )


def token_fingerprint(token: str) -> str:
    if not token:
        return "[EMPTY]"
    return f"...{token[-4:]}"


def serialize_for_log(obj: Any) -> Any:
    try:
        return json.loads(json.dumps(obj, default=str))
    except Exception:
        return str(obj)


def safe_pretty_json(obj: Any) -> str:
    try:
        return json.dumps(obj, indent=2, default=str)
    except Exception:
        return str(obj)


_REDACT_HEADERS = {"authorization", "x-api-key", "cookie", "set-cookie"}


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    return {
        k: "[REDACTED]" if k.lower() in _REDACT_HEADERS else v
        for k, v in headers.items()
    }


class AuditLogger:
    """Structured audit log for every agent call."""

    def __init__(self, agent_name: str):
        self._log = logging.getLogger(f"audit.{agent_name}")
        self._agent = agent_name

    def log_call(
        self,
        patient_id: str,
        tool_name: str,
        duration_ms: float,
        resource_ids: list[str],
    ):
        self._log.info(
            "AUDIT agent=%s patient_id=%s tool=%s duration_ms=%.1f resources=%s",
            self._agent,
            patient_id,
            tool_name,
            duration_ms,
            resource_ids,
        )

    def log_task(self, task_id: str, patient_id: str, duration_ms: float, status: str):
        self._log.info(
            "AUDIT_TASK agent=%s task_id=%s patient_id=%s duration_ms=%.1f status=%s",
            self._agent,
            task_id,
            patient_id,
            duration_ms,
            status,
        )
