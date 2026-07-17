"""Dashboard access allowlist.

D-Commie (the web dashboard) is invite-only: a Discord user must be
explicitly granted access by the bot owner (via the bot's `!dashboard
grant/revoke/list` commands) before they can use it at all, even if they
successfully log in with Discord and manage a server the bot is in.

Backed by the `dashboard_access` MongoDB collection -- one document per
authorized user, written directly by the bot's dashboard cog. This module
only reads it.
"""
from __future__ import annotations

from core.manager import mongo


async def is_authorized(user_id: int) -> bool:
    doc = await mongo.get(table="dashboard_access", id=user_id)
    return doc is not None