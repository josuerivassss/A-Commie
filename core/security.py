"""API key authentication for /json routes.

`API_KEY` already existed in config.py but was never enforced anywhere in
the original codebase. This wires it up as a FastAPI dependency applied to
every data-sensitive router (guild config, tags, reminders, audit log).
Image routes stay public, matching the original design.
"""
from fastapi import Header

from config import settings
from core.exceptions import APIException


async def require_api_key(x_api_key: str = Header(default="")) -> None:
    if not settings.API_KEY:
        # No key configured: fail closed rather than silently allowing
        # everyone through, so a forgotten .env value can't accidentally
        # expose data endpoints.
        raise APIException(status=503, error="API_KEY is not configured on the server")
    if x_api_key != settings.API_KEY:
        raise APIException(status=401, error="Invalid or missing X-API-Key header")
