"""In-memory, per-guild cooldown for the dashboard's embed sender.

Deliberately server-wide (not per-user): the goal is to prevent accidental
or malicious spam from the "Send" button, regardless of who clicks it.
Reservation happens atomically (check + write with no `await` in between,
so the asyncio event loop can't interleave two concurrent callers) BEFORE
the outbound Discord call, not after -- reserving only after a successful
send leaves a window where N concurrent requests can all pass the check
before any of them marks the guild as cooling down.

Lives in process memory -- correct as long as the API runs as a single
process (current deployment). If scaled to multiple worker processes, this
needs to move to a shared store (e.g. Redis) to stay consistent.
"""
from __future__ import annotations

import time

from config import settings

_last_sent: dict[int, float] = {}


def try_reserve(guild_id: int) -> bool:
    """Atomically checks the cooldown and reserves the slot if available.
    Returns True if the caller may proceed with sending, False if still on
    cooldown. No `await` happens between the check and the write, so this
    can't be raced by concurrent requests on the same event loop."""
    now = time.monotonic()
    last = _last_sent.get(guild_id)
    if last is not None and now - last < settings.EMBED_SEND_COOLDOWN_SECONDS:
        return False
    _last_sent[guild_id] = now
    return True


def release(guild_id: int) -> None:
    """Frees the reserved slot after a failed send, so a Discord-side
    error doesn't burn the cooldown window for a legitimate retry."""
    _last_sent.pop(guild_id, None)


def seconds_remaining(guild_id: int) -> float:
    last = _last_sent.get(guild_id)
    if last is None:
        return 0.0
    elapsed = time.monotonic() - last
    return max(0.0, settings.EMBED_SEND_COOLDOWN_SECONDS - elapsed)