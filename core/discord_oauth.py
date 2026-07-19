"""Minimal async Discord REST client for the OAuth login flow: code
exchange, the logged-in user's profile, the guilds they can manage, which
of those the bot is actually in, and a guild's text channels (for the
dashboard's channel dropdowns).
"""
from __future__ import annotations

import time
from typing import Any

import httpx

from config import settings

API_BASE = "https://discord.com/api/v10"
MANAGE_GUILD = 0x20
GUILD_TEXT, GUILD_ANNOUNCEMENT = 0, 5


class DiscordOAuthError(Exception):
    """Raised when Discord rejects a token exchange or API call."""


class DiscordOAuth:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str, bot_token: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.bot_token = bot_token
        self._bot_guild_ids_cache: tuple[float, set[int]] | None = None
        self._user_guilds_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}

    # -- OAuth2 code exchange -------------------------------------------------

    async def exchange_code(self, code: str) -> dict[str, Any]:
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{API_BASE}/oauth2/token", data=data)
        if resp.status_code != 200:
            raise DiscordOAuthError(f"Token exchange failed ({resp.status_code}): {resp.text}")
        return resp.json()

    # -- user-token calls -------------------------------------------------------

    async def get_user(self, access_token: str) -> dict[str, Any]:
        return await self._user_get("/users/@me", access_token)

    async def get_user_manageable_guilds(
        self, access_token: str, *, cache_seconds: float = 20.0
    ) -> list[dict[str, Any]]:
        """Guilds where the user is owner or has the Manage Server permission."""
        now = time.monotonic()
        cached = self._user_guilds_cache.get(access_token)
        if cached is not None and now - cached[0] < cache_seconds:
            return cached[1]

        guilds = await self._user_get("/users/@me/guilds", access_token)
        manageable = [
            g for g in guilds
            if g.get("owner") or (int(g.get("permissions", 0)) & MANAGE_GUILD) == MANAGE_GUILD
        ]
        self._user_guilds_cache[access_token] = (now, manageable)
        return manageable

    async def _user_get(self, path: str, access_token: str) -> Any:
        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_BASE}{path}", headers=headers)
        if resp.status_code != 200:
            raise DiscordOAuthError(f"GET {path} failed ({resp.status_code}): {resp.text}")
        return resp.json()

    # -- bot-token calls (ground truth for guild membership / channel lists) --

    async def get_bot_guild_ids(self, *, cache_seconds: float = 30.0) -> set[int]:
        now = time.monotonic()
        if self._bot_guild_ids_cache is not None and now - self._bot_guild_ids_cache[0] < cache_seconds:
            return self._bot_guild_ids_cache[1]

        headers = {"Authorization": f"Bot {self.bot_token}"}
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_BASE}/users/@me/guilds", headers=headers, params={"limit": 200})
        if resp.status_code != 200:
            raise DiscordOAuthError(f"Bot guild list failed ({resp.status_code}): {resp.text}")

        ids = {int(g["id"]) for g in resp.json()}
        self._bot_guild_ids_cache = (now, ids)
        return ids

    async def get_guild_text_channels(self, guild_id: int) -> list[dict[str, Any]]:
        headers = {"Authorization": f"Bot {self.bot_token}"}
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_BASE}/guilds/{guild_id}/channels", headers=headers)
        if resp.status_code != 200:
            raise DiscordOAuthError(f"Guild channels fetch failed ({resp.status_code}): {resp.text}")

        channels = resp.json()
        return sorted(
            (c for c in channels if c.get("type") in (GUILD_TEXT, GUILD_ANNOUNCEMENT)),
            key=lambda c: c.get("position", 0),
        )
    
    async def get_guild_roles(self, guild_id: int) -> list[dict[str, Any]]:
        headers = {"Authorization": f"Bot {self.bot_token}"}
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_BASE}/guilds/{guild_id}/roles", headers=headers)
        if resp.status_code != 200:
            raise DiscordOAuthError(f"Guild roles fetch failed ({resp.status_code}): {resp.text}")

        roles = resp.json()
        return sorted(
            (r for r in roles if not r.get("managed") and str(r["id"]) != str(guild_id)),
            key=lambda r: r.get("position", 0),
            reverse=True,
        )
    
    async def get_guild_emojis(self, guild_id: int) -> list[dict[str, Any]]:
        headers = {"Authorization": f"Bot {self.bot_token}"}
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_BASE}/guilds/{guild_id}/emojis", headers=headers)
        if resp.status_code != 200:
            raise DiscordOAuthError(f"Guild emojis fetch failed ({resp.status_code}): {resp.text}")
        return resp.json()


discord_oauth = DiscordOAuth(
    client_id=settings.DISCORD_CLIENT_ID,
    client_secret=settings.DISCORD_CLIENT_SECRET,
    redirect_uri=f"{settings.API_BASE_URL}/json/auth/callback",
    bot_token=settings.DISCORD_BOT_TOKEN,
)