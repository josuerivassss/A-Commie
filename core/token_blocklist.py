"""In-memory blocklist for revoked session JWTs (logout). Keyed by the
JWT's own `jti` claim, TTL'd to the token's own expiration so entries
don't accumulate forever. Same pattern as core/session_exchange.py and
core/embed_cooldown.py -- if the API ever scales to multiple worker
processes, this needs to move to a shared store (Redis/Postgres) so a
revocation on one process is visible to the others.
"""
from __future__ import annotations

import time

_revoked: dict[str, float] = {}  # jti -> expiry (unix timestamp)


def revoke(jti: str, exp: int) -> None:
    _cleanup_expired()
    _revoked[jti] = exp


def is_revoked(jti: str) -> bool:
    return jti in _revoked


def _cleanup_expired() -> None:
    now = time.time()
    expired = [j for j, exp in _revoked.items() if exp < now]
    for j in expired:
        _revoked.pop(j, None)