"""In-memory, per-guild cooldown for the dashboard's embed sender.

Deliberately server-wide (not per-user): the goal is to prevent accidental
spam from the "Send" button, regardless of who clicks it. Lives in process
memory -- correct as long as the API runs as a single process (current
deployment). If the API is ever scaled to multiple worker processes, this
would need to move to a shared store (e.g. Postgres/Redis) to stay
consistent across workers.
"""
from __future__ import annotations

import time

from config import settings

_last_sent: dict[int, float] = {}


def seconds_remaining(guild_id: int) -> float:
    last = _last_sent.get(guild_id)
    if last is None:
        return 0.0
    elapsed = time.monotonic() - last
    return max(0.0, settings.EMBED_SEND_COOLDOWN_SECONDS - elapsed)


def mark_sent(guild_id: int) -> None:
    _last_sent[guild_id] = time.monotonic()