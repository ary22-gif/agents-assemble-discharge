"""A2A application factory — mirrors reference/shared/app_factory.py.

Creates A2A v1-compliant ASGI apps for each agent. Key patches over the
installed a2a-sdk:
  - AgentCardV1: adds supportedInterfaces, overrides securitySchemes to dict[str, Any]
  - AgentExtensionV1: adds params field for SMART scope declarations
"""

import os
from typing import Any

from a2a.types import AgentCapabilities, AgentCard, AgentExtension, AgentSkill
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from pydantic import Field

FHIR_EXTENSION_URI = os.getenv(
    "FHIR_EXTENSION_URI",
    "https://app.promptopinion.ai/schemas/a2a/v1/fhir-context",
)


class AgentExtensionV1(AgentExtension):
    params: dict[str, Any] | None = Field(default=None)


class AgentCardV1(AgentCard):
    supportedInterfaces: list[dict[str, Any]] = Field(default_factory=list)
    securitySchemes: dict[str, Any] | None = None


def create_a2a_app(
    agent,
    name: str,
    description: str,
    url: str,
    port: int = 8001,
    version: str = "1.0.0",
    fhir_extension_uri: str | None = None,
    fhir_scopes: list[dict[str, Any]] | None = None,
    require_api_key: bool = True,
    skills: list[AgentSkill] | None = None,
):
    extensions = []
    if fhir_extension_uri:
        extension_params = {"scopes": fhir_scopes} if fhir_scopes else None
        extensions = [
            AgentExtensionV1(
                uri=fhir_extension_uri,
                description="FHIR context for secure patient data access",
                required=False,
                params=extension_params,
            )
        ]

    if require_api_key:
        security_schemes = {
            "apiKey": {
                "apiKeySecurityScheme": {
                    "name": "X-API-Key",
                    "location": "header",
                    "description": "API key required to access this agent.",
                }
            }
        }
        security: list[dict] | None = [{"apiKey": []}]
    else:
        security_schemes = None
        security = None

    agent_card = AgentCardV1(  # type: ignore[call-arg]
        name=name,
        description=description,
        url=url,
        version=version,
        defaultInputModes=["text/plain"],
        defaultOutputModes=["application/json", "text/plain"],
        capabilities=AgentCapabilities(  # type: ignore[call-arg]
            streaming=False,
            pushNotifications=False,
            stateTransitionHistory=False,
            extensions=extensions,  # type: ignore[arg-type]
        ),
        supportedInterfaces=[
            {"url": url, "protocolBinding": "JSONRPC", "protocolVersion": "1.0"},
        ],
        skills=skills or [],
        securitySchemes=security_schemes,
        security=security,
    )

    from shared.middleware import ApiKeyMiddleware

    app = to_a2a(agent, port=port, agent_card=agent_card)
    if require_api_key:
        app.add_middleware(ApiKeyMiddleware)
    return app
