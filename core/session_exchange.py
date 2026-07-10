"""Short-lived, single-use exchange codes for handing a session token off
to the frontend without ever putting the token itself in a URL.

Putting a real bearer token in a redirect URL's query string is a known
anti-pattern: it lands in browser history, in Referer headers of any
subsequent cross-origin request, and matches a URL shape that phishing/
credential-theft pages also produce -- which is exactly why security
scanners (e.g. browser extensions like Malwarebytes) sometimes flag it as
suspicious. An opaque, 60-second, single-use code carries none of that risk
even if leaked, and is the same pattern OAuth's own authorization code
already uses.
"""
from __future__ import annotations

import secrets
import time

_TTL_SECONDS = 60
_store: dict[str, tuple[float, str]] = {}


def create_exchange_code(token: str) -> str:
    _cleanup_expired()
    code = secrets.token_urlsafe(32)
    _store[code] = (time.monotonic(), token)
    return code


def redeem_exchange_code(code: str) -> str | None:
    """Returns the token and deletes the code (single-use), or None if the
    code is missing/expired/already used."""
    entry = _store.pop(code, None)
    if entry is None:
        return None
    created_at, token = entry
    if time.monotonic() - created_at > _TTL_SECONDS:
        return None
    return token


def _cleanup_expired() -> None:
    now = time.monotonic()
    expired = [code for code, (created_at, _) in _store.items() if now - created_at > _TTL_SECONDS]
    for code in expired:
        _store.pop(code, None)