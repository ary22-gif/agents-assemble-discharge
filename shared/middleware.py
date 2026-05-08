"""API key middleware — mirrors reference/shared/middleware.py."""
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

AGENT_API_KEY = os.getenv("AGENT_API_KEY", "")
PUBLIC_PATHS  = {"/", "/.well-known/agent.json", "/.well-known/agent-card.json"}


class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)
        if not AGENT_API_KEY:
            return await call_next(request)
        key = request.headers.get("X-API-Key", "")
        if key != AGENT_API_KEY:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)
