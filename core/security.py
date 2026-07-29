"""API key authentication for /json routes.
...
"""
import secrets
from fastapi import Header
from config import settings
from core.exceptions import APIException


async def require_api_key(x_api_key: str = Header(default="")) -> None:
    if not settings.API_KEY:
        raise APIException(status=503, error="API_KEY is not configured on the server")
    if not secrets.compare_digest(x_api_key, settings.API_KEY):
        raise APIException(status=401, error="Invalid or missing X-API-Key header")