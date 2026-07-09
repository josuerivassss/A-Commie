from fastapi import APIRouter, Depends
from core.access import require_access
from core.discord_oauth import discord_oauth
from core.manager import mongo
from schemas.requests import GuildConfigUpdate
from schemas.responses import HTTPResponse

router = APIRouter(prefix="/json/guilds", tags=["Guilds"], dependencies=[Depends(require_access)])

@router.get(
    "/{guild_id}",
    description="Returns a guild's full configuration document (prefix, language, welcome/leave settings).",
    response_model=HTTPResponse,
)
async def get_guild_config(guild_id: int):
    doc = await mongo.get(table="guilds", id=guild_id)
    return HTTPResponse.use(data=doc or {})


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
        await mongo.set(table="guilds", id=guild_id, path=field_map[field], value=value)

    doc = await mongo.get(table="guilds", id=guild_id)
    return HTTPResponse.use(data=doc)


@router.get(
    "/{guild_id}/channels",
    description="Lists the guild's text/announcement channels (for dashboard channel dropdowns).",
    response_model=HTTPResponse,
)
async def get_guild_channels(guild_id: int):
    channels = await discord_oauth.get_guild_text_channels(guild_id)
    return HTTPResponse.use(data=[{"id": c["id"], "name": c["name"]} for c in channels])