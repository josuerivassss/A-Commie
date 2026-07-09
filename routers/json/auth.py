"""Discord OAuth2 login: the frontend sends the user straight to Discord
(no endpoint needed for that part, since it needs no secret); this only
handles the callback (needs CLIENT_SECRET, must stay server-side) and the
authenticated /me endpoint the frontend calls afterward.
"""
from urllib.parse import urlencode

import jwt as pyjwt
from fastapi import APIRouter, Header

from config import settings
from core.discord_oauth import DiscordOAuthError, discord_oauth
from core.exceptions import APIException
from core.jwt_auth import create_jwt, decode_jwt
from schemas.responses import HTTPResponse
from fastapi.responses import RedirectResponse

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
    query = urlencode({"token": session_token})
    return RedirectResponse(f"{settings.FRONTEND_URL}/auth/callback?{query}")


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