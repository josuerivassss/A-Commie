"""Auth dependencies for /json routes.

Two layers apply to every dashboard request:
  1. Credential check -- EITHER an `X-API-Key` (trusted server-to-server
     caller) OR a valid `Authorization: Bearer <jwt>` from a Discord login.
  2. Dashboard allowlist check -- even with a valid Discord login, the
     user's ID must be in the `dashboard_access` collection (granted via
     the bot's `!dashboard grant` command). API-key callers skip this
     layer, since they're trusted server-to-server integrations, not
     end-user dashboard sessions.

Guild-scoped routes additionally require the user to manage that guild AND
the bot to actually be present there. User-scoped routes (e.g. a user's own
reminders) just require the token's subject to match the path's user_id.
"""
from __future__ import annotations

from typing import Any

import jwt as pyjwt
import secrets
from fastapi import Header

from config import settings
from core.dashboard_access import is_authorized
from core.discord_oauth import discord_oauth
from core.exceptions import APIException
from core.jwt_auth import decode_jwt


def _is_valid_api_key(x_api_key: str) -> bool:
    return bool(settings.API_KEY) and secrets.compare_digest(x_api_key, settings.API_KEY)

def _decode_bearer(authorization: str) -> dict[str, Any] | None:
    if not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    try:
        return decode_jwt(token)
    except pyjwt.PyJWTError:
        return None


async def _require_authorized_user(authorization: str) -> dict[str, Any]:
    """Shared by every dependency below: valid JWT + on the dashboard allowlist."""
    payload = _decode_bearer(authorization)
    if payload is None:
        raise APIException(status=401, error="Missing or invalid credentials")
    if not await is_authorized(int(payload["sub"])):
        raise APIException(status=403, error="dashboard_access_denied")
    return payload


async def require_access(
    guild_id: int,
    x_api_key: str = Header(default=""),
    authorization: str = Header(default=""),
) -> None:
    """For routes scoped to a specific guild_id path parameter."""
    if _is_valid_api_key(x_api_key):
        return

    payload = await _require_authorized_user(authorization)

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

    payload = await _require_authorized_user(authorization)
    if int(payload["sub"]) != user_id:
        raise APIException(status=401, error="Missing or invalid credentials")


async def resolve_identity(
    x_api_key: str = Header(default=""),
    authorization: str = Header(default=""),
) -> dict[str, Any] | None:
    """For routes that only know which guild/user a resource belongs to
    after looking it up. Returns None for a trusted API-key caller; returns
    the decoded JWT payload for a logged-in, allowlisted user."""
    if _is_valid_api_key(x_api_key):
        return None
    return await _require_authorized_user(authorization)