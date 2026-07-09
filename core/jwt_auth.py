"""Our own short-lived session token, issued after a successful Discord
OAuth login. Not Discord's token directly -- ours also embeds the user's
Discord access token so `core.access` can re-check live guild membership
without a second round of OAuth.
"""
from __future__ import annotations

import time
from typing import Any

import jwt

from config import settings

ALGORITHM = "HS256"


def create_jwt(*, user_id: int, username: str, avatar: str | None, discord_access_token: str) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "username": username,
        "avatar": avatar,
        "discord_token": discord_access_token,
        "iat": now,
        "exp": now + settings.JWT_EXPIRES_MINUTES * 60,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


def decode_jwt(token: str) -> dict[str, Any]:
    """Raises jwt.PyJWTError (expired/invalid/tampered) -- callers must catch it."""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])