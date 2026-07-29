"""Guild configuration endpoints: prefix, language, welcome/leave messages,
and starboard -- everything stored under a single `guilds` document per
guild_id in MongoDB. Consolidated here (rather than split across routers)
since it's all reads/writes against the same document.
"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from core.access import require_access
from core.discord_oauth import discord_oauth
from core.manager import mongo
from schemas.requests import GuildConfigUpdate
from schemas.responses import HTTPResponse
from schemas.requests import SNOWFLAKE_MAX, SNOWFLAKE_MIN

router = APIRouter(prefix="/json/guilds", tags=["Guilds"], dependencies=[Depends(require_access)])

DEFAULT_STARBOARD = {
    "enabled": False,
    "channel_id": None,
    "emoji": "\u2b50",
    "threshold": 3,
    "count_self_stars": False,
}

class StarboardUpdate(BaseModel):
    enabled: Optional[bool] = None
    channel_id: Optional[int] = Field(default=None, ge=SNOWFLAKE_MIN, le=SNOWFLAKE_MAX)
    emoji: Optional[str] = Field(default=None, max_length=60)
    threshold: Optional[int] = Field(default=None, ge=1, le=500)
    count_self_stars: Optional[bool] = None


def _serialize_guild(doc: dict) -> dict:
    # Cast channel IDs to str before they leave the API -- prevents JS
    # Number precision loss on the frontend for snowflakes >= 2^53.
    serialized = dict(doc)
    for section in ("welcome", "leave"):
        block = serialized.get(section)
        if isinstance(block, dict) and block.get("channel") is not None:
            block = dict(block)
            block["channel"] = str(block["channel"])
            serialized[section] = block
    return serialized


def _serialize_starboard(doc: dict) -> dict:
    merged = {**DEFAULT_STARBOARD, **doc}
    merged["channel_id"] = str(merged["channel_id"]) if merged["channel_id"] is not None else None
    return merged


@router.get(
    "/{guild_id}",
    description="Returns a guild's full configuration document (prefix, language, welcome/leave settings).",
    response_model=HTTPResponse,
)
async def get_guild_config(guild_id: int):
    doc = await mongo.get(table="guilds", id=guild_id)
    return HTTPResponse.use(data=_serialize_guild(doc or {}))

@router.patch(
    "/{guild_id}",
    description="Partially updates a guild's configuration. Only provided fields are changed.",
    response_model=HTTPResponse,
)
async def update_guild_config(guild_id: int, body: GuildConfigUpdate):
    updates = body.model_dump(exclude_none=True)
    if not updates:
        return HTTPResponse.use(status=400, error="No fields provided to update")

    field_map = {
        "prefix": "prefix",
        "language": "language",
        "welcome_enabled": "welcome.enabled",
        "welcome_channel_id": "welcome.channel",
        "welcome_message": "welcome.message",
        "leave_enabled": "leave.enabled",
        "leave_channel_id": "leave.channel",
        "leave_message": "leave.message",
    }
    for field, value in updates.items():
        path = field_map[field]
        # Empty prefix means "use the bot's default" -- that only works if
        # the field is actually removed, not set to "" (an empty string is
        # still a valid, non-None value, so the bot would never fall back).
        if field == "prefix" and value == "":
            await mongo.delete_field(table="guilds", id=guild_id, path=path)
        else:
            await mongo.set(table="guilds", id=guild_id, path=path, value=value)

    doc = await mongo.get(table="guilds", id=guild_id)
    return HTTPResponse.use(data=_serialize_guild(doc or {}))


@router.get(
    "/{guild_id}/channels",
    description="Lists the guild's text/announcement channels (for dashboard channel dropdowns).",
    response_model=HTTPResponse,
)
async def get_guild_channels(guild_id: int):
    channels = await discord_oauth.get_guild_text_channels(guild_id)
    return HTTPResponse.use(data=[{"id": c["id"], "name": c["name"]} for c in channels])

@router.get(
    "/{guild_id}/roles",
    description="Lists the guild's assignable roles (for the autoroles selector).",
    response_model=HTTPResponse,
)
async def get_guild_roles(guild_id: int):
    roles = await discord_oauth.get_guild_roles(guild_id)
    return HTTPResponse.use(data=[{"id": r["id"], "name": r["name"], "color": r.get("color", 0)} for r in roles])

@router.get(
    "/{guild_id}/emojis",
    description="Lists the guild's non-animated custom emojis usable by everyone (for the starboard emoji picker).",
    response_model=HTTPResponse,
)
async def get_guild_emojis(guild_id: int):
    emojis = await discord_oauth.get_guild_emojis(guild_id)
    return HTTPResponse.use(data=[
        {"id": e["id"], "name": e["name"], "url": f"https://cdn.discordapp.com/emojis/{e['id']}.png"}
        for e in emojis
        if not e.get("animated") and not e.get("roles")
    ])

@router.get(
    "/{guild_id}/starboard",
    description="Returns a guild's starboard configuration.",
    response_model=HTTPResponse,
)
async def get_starboard(guild_id: int):
    doc = await mongo.get(table="guilds", id=guild_id, path="starboard") or {}
    return HTTPResponse.use(data=_serialize_starboard(doc))

@router.patch(
    "/{guild_id}/starboard",
    description="Partially updates a guild's starboard configuration.",
    response_model=HTTPResponse,
)
async def update_starboard(guild_id: int, body: StarboardUpdate):
    updates = body.model_dump(exclude_none=True)
    if not updates:
        return HTTPResponse.use(status=400, error="No fields provided to update")
    for field, value in updates.items():
        await mongo.set(table="guilds", id=guild_id, path=f"starboard.{field}", value=value)
    doc = await mongo.get(table="guilds", id=guild_id, path="starboard") or {}
    return HTTPResponse.use(data=_serialize_starboard(doc))