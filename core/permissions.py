"""Manual reimplementation of Discord's channel permission overwrite
algorithm (base role permissions -> @everyone overwrite -> role overwrites
-> member overwrite), used to determine whether the bot can actually post
in a given channel before offering it in the dashboard's channel picker.

Mirrors https://discord.com/developers/docs/topics/permissions#permission-overwrites
"""
from __future__ import annotations

from typing import Any

VIEW_CHANNEL = 1 << 10
SEND_MESSAGES = 1 << 11
ADD_REACTIONS = 1 << 6
EMBED_LINKS = 1 << 14
ADMINISTRATOR = 1 << 3
CREATE_PRIVATE_THREADS = 1 << 36
SEND_MESSAGES_IN_THREADS = 1 << 38
CHANGE_NICKNAME = 1 << 26

REQUIRED_TO_SEND_EMBED = VIEW_CHANNEL | SEND_MESSAGES | EMBED_LINKS

# The ticket channel now serves both roles at once (panel location + thread
# parent), so it needs the union of "can post a normal embed here" and
# "can create/reply inside private threads here".
REQUIRED_FOR_TICKET_CHANNEL = (
    VIEW_CHANNEL | SEND_MESSAGES | EMBED_LINKS | CREATE_PRIVATE_THREADS | SEND_MESSAGES_IN_THREADS
)


def compute_channel_permissions(
    *,
    member_role_ids: set[str],
    bot_user_id: str,
    everyone_role: dict[str, Any],
    guild_roles: list[dict[str, Any]],
    overwrites: list[dict[str, Any]],
) -> int:
    """Effective permission bitfield for a member in a specific channel.
    `member_role_ids` holds the member's own assigned roles (Discord's
    member object omits @everyone implicitly)."""
    base = int(everyone_role["permissions"])
    for role in guild_roles:
        if role["id"] in member_role_ids:
            base |= int(role["permissions"])

    if base & ADMINISTRATOR:
        return ~0  # Administrator bypasses every channel overwrite.

    everyone_overwrite = next(
        (o for o in overwrites if o["type"] == 0 and o["id"] == everyone_role["id"]), None
    )
    if everyone_overwrite:
        base &= ~int(everyone_overwrite["deny"])
        base |= int(everyone_overwrite["allow"])

    allow, deny = 0, 0
    for overwrite in overwrites:
        if overwrite["type"] == 0 and overwrite["id"] in member_role_ids:
            allow |= int(overwrite["allow"])
            deny |= int(overwrite["deny"])
    base &= ~deny
    base |= allow

    member_overwrite = next(
        (o for o in overwrites if o["type"] == 1 and o["id"] == bot_user_id), None
    )
    if member_overwrite:
        base &= ~int(member_overwrite["deny"])
        base |= int(member_overwrite["allow"])

    return base


def can_send_embeds(permissions: int) -> bool:
    return (permissions & REQUIRED_TO_SEND_EMBED) == REQUIRED_TO_SEND_EMBED


def can_host_tickets(permissions: int) -> bool:
    return (permissions & REQUIRED_FOR_TICKET_CHANNEL) == REQUIRED_FOR_TICKET_CHANNEL

def can_change_nickname(permissions: int) -> bool:
    return bool(permissions & (CHANGE_NICKNAME | ADMINISTRATOR))