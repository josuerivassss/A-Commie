"""Minimal async Discord REST client for the OAuth login flow: code
exchange, the logged-in user's profile, the guilds they can manage, which
of those the bot is actually in, a guild's text channels/roles/emojis (for
the dashboard's selectors), and sending messages/reactions/panels on the
bot's behalf (embed sender, ticket panel).
"""
from __future__ import annotations

import asyncio
import time
from typing import Any
from urllib.parse import quote

import httpx

from config import settings
from core.permissions import can_host_tickets, can_send_embeds, compute_channel_permissions

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
        self._bot_user_id: str | None = None

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

    async def get_bot_user_id(self) -> str:
        """The bot's own Discord user ID -- never changes for a running
        process, so it's cached indefinitely once fetched."""
        if self._bot_user_id is None:
            headers = {"Authorization": f"Bot {self.bot_token}"}
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{API_BASE}/users/@me", headers=headers)
            if resp.status_code != 200:
                raise DiscordOAuthError(f"Bot identity fetch failed ({resp.status_code}): {resp.text}")
            self._bot_user_id = resp.json()["id"]
        return self._bot_user_id

    async def get_guild_member(self, guild_id: int, user_id: str) -> dict[str, Any]:
        headers = {"Authorization": f"Bot {self.bot_token}"}
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_BASE}/guilds/{guild_id}/members/{user_id}", headers=headers)
        if resp.status_code != 200:
            raise DiscordOAuthError(f"Guild member fetch failed ({resp.status_code}): {resp.text}")
        return resp.json()

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

    async def _get_raw_guild_roles(self, guild_id: int) -> list[dict[str, Any]]:
        headers = {"Authorization": f"Bot {self.bot_token}"}
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_BASE}/guilds/{guild_id}/roles", headers=headers)
        if resp.status_code != 200:
            raise DiscordOAuthError(f"Guild roles fetch failed ({resp.status_code}): {resp.text}")
        return resp.json()

    async def get_guild_roles(self, guild_id: int) -> list[dict[str, Any]]:
        roles = await self._get_raw_guild_roles(guild_id)
        return sorted(
            (r for r in roles if not r.get("managed") and str(r["id"]) != str(guild_id)),
            key=lambda r: r.get("position", 0),
            reverse=True,
        )

    async def _compute_channel_permissions_batch(self, guild_id: int) -> list[tuple[dict[str, Any], int]]:
        """Shared groundwork for any endpoint needing real per-channel
        permissions (embeds sender, tickets) -- fetches bot identity,
        member, roles and channels once, then computes the effective
        permission bitfield for each channel."""
        bot_user_id = await self.get_bot_user_id()
        member, roles, channels = await asyncio.gather(
            self.get_guild_member(guild_id, bot_user_id),
            self._get_raw_guild_roles(guild_id),
            self.get_guild_text_channels(guild_id),
        )
        member_role_ids = set(member.get("roles", []))
        everyone_role = next(
            (r for r in roles if r["id"] == str(guild_id)), {"id": str(guild_id), "permissions": "0"}
        )

        result = []
        for channel in channels:
            permissions = compute_channel_permissions(
                member_role_ids=member_role_ids,
                bot_user_id=bot_user_id,
                everyone_role=everyone_role,
                guild_roles=roles,
                overwrites=channel.get("permission_overwrites", []),
            )
            result.append((channel, permissions))
        return result

    async def get_sendable_text_channels(self, guild_id: int) -> list[dict[str, Any]]:
        """Text/announcement channels annotated with whether the bot can
        actually post an embed there, computed from real permission
        overwrites rather than just channel type/visibility."""
        pairs = await self._compute_channel_permissions_batch(guild_id)
        return [{"id": c["id"], "name": c["name"], "can_send": can_send_embeds(perms)} for c, perms in pairs]

    async def get_ticket_channels(self, guild_id: int) -> list[dict[str, Any]]:
        """Same channel list, annotated for two different ticket-related
        needs: hosting the parent channel (thread creation) and posting
        the panel message (a normal embed)."""
        pairs = await self._compute_channel_permissions_batch(guild_id)
        return [
            {
                "id": c["id"],
                "name": c["name"],
                "can_host_tickets": can_host_tickets(perms),
                "can_send_panel": can_send_embeds(perms),
            }
            for c, perms in pairs
        ]

    async def get_guild_emojis(self, guild_id: int) -> list[dict[str, Any]]:
        headers = {"Authorization": f"Bot {self.bot_token}"}
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_BASE}/guilds/{guild_id}/emojis", headers=headers)
        if resp.status_code != 200:
            raise DiscordOAuthError(f"Guild emojis fetch failed ({resp.status_code}): {resp.text}")
        return resp.json()

    # -- message/reaction/panel sending (embed sender, tickets) ---------------

    async def send_message(
        self, channel_id: int, *, content: str | None, embeds: list[dict[str, Any]],
        components: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Bot {self.bot_token}"}
        payload: dict[str, Any] = {
            "embeds": embeds,
            "allowed_mentions": {"parse": ["roles", "users"]},
        }
        if content:
            payload["content"] = content
        if components:
            payload["components"] = components
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{API_BASE}/channels/{channel_id}/messages", headers=headers, json=payload)
        if resp.status_code not in (200, 201):
            raise DiscordOAuthError(f"Message send failed ({resp.status_code}): {resp.text}")
        return resp.json()

    async def add_reaction(self, channel_id: int, message_id: str, emoji: str) -> bool:
        headers = {"Authorization": f"Bot {self.bot_token}"}
        encoded = quote(emoji, safe="")
        async with httpx.AsyncClient() as client:
            resp = await client.put(
                f"{API_BASE}/channels/{channel_id}/messages/{message_id}/reactions/{encoded}/@me", headers=headers
            )
        return resp.status_code == 204


discord_oauth = DiscordOAuth(
    client_id=settings.DISCORD_CLIENT_ID,
    client_secret=settings.DISCORD_CLIENT_SECRET,
    redirect_uri=f"{settings.API_BASE_URL}/json/auth/callback",
    bot_token=settings.DISCORD_BOT_TOKEN,
)