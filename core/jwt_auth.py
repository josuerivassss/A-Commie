"""Our own short-lived session token, issued after a successful Discord
OAuth login. Not Discord's token directly -- ours also embeds the user's
Discord access token so `core.access` can re-check live guild membership
without a second round of OAuth.
"""
from __future__ import annotations

import secrets
import time
from typing import Any

import jwt

from config import settings
from core.token_blocklist import is_revoked

ALGORITHM = "HS256"


def create_jwt(*, user_id: int, username: str, avatar: str | None, discord_access_token: str) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "username": username,
        "avatar": avatar,
        "discord_token": discord_access_token,
        "jti": secrets.token_urlsafe(16),
        "iat": now,
        "exp": now + settings.JWT_EXPIRES_MINUTES * 60,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


def decode_jwt(token: str) -> dict[str, Any]:
    """Raises jwt.PyJWTError (expired/invalid/tampered/revoked) -- callers must catch it."""
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
    if is_revoked(payload.get("jti", "")):
        raise jwt.InvalidTokenError("Token has been revoked")
    return payload