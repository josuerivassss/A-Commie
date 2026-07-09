"""Auth dependencies for /json routes.

Two credential types are accepted throughout, so existing server-to-server
integrations keep working while the new dashboard uses per-user login:
  - `X-API-Key` header matching the configured API_KEY (trusted server), or
  - `Authorization: Bearer <jwt>` from a logged-in user.

Guild-scoped routes additionally require the user to manage that guild AND
the bot to actually be present there. User-scoped routes (e.g. a user's own
reminders) just require the token's subject to match the path's user_id.
Routes that only learn "which guild/user does this resource belong to"
after a DB lookup (e.g. deleting a reminder by id) use `resolve_identity`
and check ownership themselves once they have the row in hand.
"""
from __future__ import annotations

from typing import Any

import jwt as pyjwt
from fastapi import Header

from config import settings
from core.discord_oauth import discord_oauth
from core.exceptions import APIException
from core.jwt_auth import decode_jwt


def _is_valid_api_key(x_api_key: str) -> bool:
    return bool(settings.API_KEY) and x_api_key == settings.API_KEY


def _decode_bearer(authorization: str) -> dict[str, Any] | None:
    if not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    try:
        return decode_jwt(token)
    except pyjwt.PyJWTError:
        return None


async def require_access(
    guild_id: int,
    x_api_key: str = Header(default=""),
    authorization: str = Header(default=""),
) -> None:
    """For routes scoped to a specific guild_id path parameter."""
    if _is_valid_api_key(x_api_key):
        return

    payload = _decode_bearer(authorization)
    if payload is None:
        raise APIException(status=401, error="Missing or invalid credentials")

    manageable = await discord_oauth.get_user_manageable_guilds(payload["discord_token"])
    if not any(int(g["id"]) == guild_id for g in manageable):
        raise APIException(status=403, error="You do not manage that server")

    bot_guild_ids = await discord_oauth.get_bot_guild_ids()
    if guild_id not in bot_guild_ids:
        raise APIException(status=403, error="The bot is not in that server")


async def require_self_or_api_key(
    user_id: int,
    x_api_key: str = Header(default=""),
    authorization: str = Header(default=""),
) -> None:
    """For routes scoped to a specific user_id path parameter (no guild context)."""
    if _is_valid_api_key(x_api_key):
        return

    payload = _decode_bearer(authorization)
    if payload is None or int(payload["sub"]) != user_id:
        raise APIException(status=401, error="Missing or invalid credentials")


async def resolve_identity(
    x_api_key: str = Header(default=""),
    authorization: str = Header(default=""),
) -> dict[str, Any] | None:
    """For routes that only know which guild/user a resource belongs to
    after looking it up (e.g. deleting a reminder by its id, not by
    guild/user). Returns None for a trusted API-key caller (skip further
    checks); returns the decoded JWT payload for a logged-in user (the
    route must then verify ownership itself with the row in hand)."""
    if _is_valid_api_key(x_api_key):
        return None

    payload = _decode_bearer(authorization)
    if payload is None:
        raise APIException(status=401, error="Missing or invalid credentials")
    return payload