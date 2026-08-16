"""Pod-to-pod gate for the SaaS deployment behind Orchestrator.

Uses EXOBRAIN_INTERNAL_API_KEY (X-API-Key). This is not OPENAI_API_KEY.
OSS docker / local leave it unset so the standalone frontend can call the engine.
"""

from __future__ import annotations

import os

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

_PUBLIC_EXACT = {"/health", "/", "/docs", "/openapi.json", "/redoc"}


class InternalKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in _PUBLIC_EXACT or path.startswith("/m"):
            return await call_next(request)

        expected = os.getenv("EXOBRAIN_INTERNAL_API_KEY", "").strip()
        require = os.getenv("EXOBRAIN_REQUIRE_INTERNAL_KEY", "").strip().lower() in {
            "1",
            "true",
            "yes",
        }
        if not expected and not require:
            return await call_next(request)
        if not expected:
            return JSONResponse({"detail": "Exobrain internal key is not configured"}, status_code=500)
        if request.headers.get("X-API-Key") != expected:
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        return await call_next(request)
