"""Discord OAuth2 login: the frontend sends the user straight to Discord
(no endpoint needed for that part, since it needs no secret); this only
handles the callback (needs CLIENT_SECRET, must stay server-side) and the
authenticated /me endpoint the frontend calls afterward.

The callback hands off a short-lived, single-use exchange code rather than
the session token itself -- see core/session_exchange.py for why.
"""
from urllib.parse import urlencode

import jwt as pyjwt
from fastapi import APIRouter, Header
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from config import settings
from core.discord_oauth import DiscordOAuthError, discord_oauth
from core.exceptions import APIException
from core.jwt_auth import create_jwt, decode_jwt
from core.session_exchange import create_exchange_code, redeem_exchange_code
from schemas.responses import HTTPResponse

router = APIRouter(prefix="/json/auth", tags=["Auth"])


@router.get("/callback")
async def callback(code: str | None = None, error: str | None = None):
    """Discord redirects here after the user approves the login prompt.
    Register this exact URL (API_BASE_URL + /json/auth/callback) in the
    Discord Developer Portal's OAuth2 Redirects."""
    if error or not code:
        return RedirectResponse(f"{settings.FRONTEND_URL}/login?error=1")

    try:
        token_data = await discord_oauth.exchange_code(code)
        user = await discord_oauth.get_user(token_data["access_token"])
    except DiscordOAuthError:
        return RedirectResponse(f"{settings.FRONTEND_URL}/login?error=1")

    session_token = create_jwt(
        user_id=int(user["id"]),
        username=user["username"],
        avatar=user.get("avatar"),
        discord_access_token=token_data["access_token"],
    )
    # Hand off a one-time exchange code instead of the token itself, so the
    # real session token never appears in a URL/browser history/Referer header.
    exchange_code = create_exchange_code(session_token)
    query = urlencode({"session_code": exchange_code})
    return RedirectResponse(f"{settings.FRONTEND_URL}/auth/callback?{query}")


class ExchangeRequest(BaseModel):
    session_code: str


@router.post("/exchange")
async def exchange(body: ExchangeRequest):
    """Redeems a one-time code (from /callback's redirect) for the actual
    session token, returned in the response body -- never in a URL."""
    token = redeem_exchange_code(body.session_code)
    if token is None:
        raise APIException(status=400, error="Invalid or expired login code")
    return HTTPResponse.use(data={"token": token})


@router.get("/me")
async def me(authorization: str = Header(default="")):
    """Returns the logged-in user's profile plus every guild they can
    manage, flagged with whether the bot is already in each one."""
    if not authorization.startswith("Bearer "):
        raise APIException(status=401, error="Missing credentials")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = decode_jwt(token)
    except pyjwt.PyJWTError as exc:
        raise APIException(status=401, error="Invalid or expired session") from exc

    manageable = await discord_oauth.get_user_manageable_guilds(payload["discord_token"])
    bot_guild_ids = await discord_oauth.get_bot_guild_ids()
    guilds = [
        {
            "id": g["id"],
            "name": g["name"],
            "icon": g.get("icon"),
            "has_bot": int(g["id"]) in bot_guild_ids,
        }
        for g in manageable
    ]

    return HTTPResponse.use(data={
        "user": {"id": payload["sub"], "username": payload["username"], "avatar": payload["avatar"]},
        "guilds": guilds,
    })