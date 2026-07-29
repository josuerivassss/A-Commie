"""Ticket system configuration and panel publishing -- mirrors the bot's
`guilds.tickets` document (bcommie/cogs/tickets.py). A single "tickets
channel" now serves both as the panel's location and as the parent for
new private threads -- there's no separate parent_channel_id anymore.

`panel_channel_id`/`panel_message_id` are read-only from the dashboard's
perspective: they're only ever written as a side effect of successfully
publishing a panel (POST /panel), never through a plain config PATCH,
since setting the channel without actually posting a panel there would
leave the UI claiming a panel exists when it doesn't. Publishing a new
panel automatically retires the previous one (only one active panel at a
time), matching the bot's own `!ticket channel` behavior.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from core.access import require_access
from core.discord_oauth import DiscordOAuthError, discord_oauth
from core.exceptions import APIException
from core.manager import mongo
from schemas.responses import HTTPResponse
from schemas.requests import SNOWFLAKE_MAX, SNOWFLAKE_MIN

router = APIRouter(prefix="/json/guilds/{guild_id}/tickets", tags=["Tickets"], dependencies=[Depends(require_access)])

DEFAULT_TICKETS = {
    "enabled": False,
    "staff_role_id": None,
    "welcome_message": "Welcome {user.mention}! Support will be with you shortly.",
    "panel_channel_id": None,
    "panel_message_id": None,
}

MIN_MESSAGE_LENGTH = 5
MAX_MESSAGE_LENGTH = 1800

# Mirrors locales/en.json and es.json's tickets.panelTitle/panelDescription
# in the bot repo -- the API has no access to those JSON files (separate
# repo/process), so the two strings actually used in the panel embed are
# duplicated here deliberately, matching the bot's current wording exactly.
PANEL_TEXT = {
    "en": {"title": "Need help?", "description": "Click the button below to open a private ticket with our staff."},
    "es": {"title": "\u00bfNecesitas ayuda?", "description": "Haz clic en el bot\u00f3n de abajo para abrir un ticket privado con nuestro staff."},
}
PANEL_BUTTON_LABEL = "Open"
PANEL_BUTTON_EMOJI = "\U0001f3ab"
PANEL_COLOR = 0x992D22  # discord.Colour.dark_red(), matches the bot's own panel command

BOT_AVATAR_URL = "https://i.imgur.com/J7qH6M1.png"
TICKETS_BANNER_URL = "https://i.imgur.com/k9zLycU.png"

class TicketsUpdate(BaseModel):
    enabled: Optional[bool] = None
    staff_role_id: Optional[int] = Field(default=None, ge=SNOWFLAKE_MIN, le=SNOWFLAKE_MAX)
    welcome_message: Optional[str] = Field(default=None, min_length=MIN_MESSAGE_LENGTH, max_length=MAX_MESSAGE_LENGTH)


class PostPanelRequest(BaseModel):
    channel_id: int = Field(ge=SNOWFLAKE_MIN, le=SNOWFLAKE_MAX)


def _serialize(doc: dict) -> dict:
    merged = {**DEFAULT_TICKETS, **doc}
    merged["staff_role_id"] = str(merged["staff_role_id"]) if merged["staff_role_id"] is not None else None
    merged["panel_channel_id"] = str(merged["panel_channel_id"]) if merged["panel_channel_id"] is not None else None
    merged["panel_message_id"] = str(merged["panel_message_id"]) if merged["panel_message_id"] is not None else None
    return merged


@router.get("")
async def get_tickets(guild_id: int):
    doc = await mongo.get(table="guilds", id=guild_id, path="tickets") or {}
    return HTTPResponse.use(data=_serialize(doc))


@router.patch("")
async def update_tickets(guild_id: int, body: TicketsUpdate):
    updates = body.model_dump(exclude_none=True)
    if not updates:
        return HTTPResponse.use(status=400, error="No fields provided to update")
    for field, value in updates.items():
        await mongo.set(table="guilds", id=guild_id, path=f"tickets.{field}", value=value)
    doc = await mongo.get(table="guilds", id=guild_id, path="tickets") or {}
    return HTTPResponse.use(data=_serialize(doc))


@router.get("/channels")
async def get_ticket_channels(guild_id: int):
    channels = await discord_oauth.get_ticket_channels(guild_id)
    return HTTPResponse.use(data=channels)


@router.post("/panel")
async def post_panel(guild_id: int, body: PostPanelRequest):
    channels = await discord_oauth.get_ticket_channels(guild_id)
    target = next((c for c in channels if int(c["id"]) == body.channel_id), None)
    if target is None:
        raise APIException(status=404, error="Channel not found in this server")
    if not target["can_host_tickets"]:
        raise APIException(
            status=403,
            error="The bot needs View Channel, Send Messages, Embed Links, Create Private Threads, "
                  "and Send Messages in Threads there",
        )

    doc = await mongo.get(table="guilds", id=guild_id, path="tickets") or {}
    config = {**DEFAULT_TICKETS, **doc}
    if config["panel_channel_id"] and config["panel_message_id"]:
        await discord_oauth.delete_message(config["panel_channel_id"], config["panel_message_id"])

    language = await mongo.get(table="guilds", id=guild_id, path="language") or "en"
    text = PANEL_TEXT.get(language, PANEL_TEXT["en"])
    embed = {"title": text["title"], "description": text["description"], "color": PANEL_COLOR, "footer": {"text": "Commie Tickets", "icon_url": BOT_AVATAR_URL}, "image": {"url": TICKETS_BANNER_URL}}
    components = [{
        "type": 1,
        "components": [{
            "type": 2, "style": 1, "label": PANEL_BUTTON_LABEL,
            "custom_id": "tickets:open", "emoji": {"name": PANEL_BUTTON_EMOJI},
        }],
    }]

    try:
        message = await discord_oauth.send_message(
            body.channel_id, content=None, embeds=[embed], components=components
        )
    except DiscordOAuthError as exc:
        raise APIException(status=502, error=f"Discord rejected the panel message: {exc}") from None

    await mongo.set(
        table="guilds", id=guild_id,
        data={
            "tickets.enabled": True,
            "tickets.panel_channel_id": body.channel_id,
            "tickets.panel_message_id": int(message["id"]),
        },
    )
    return HTTPResponse.use(data={
        "message_id": message["id"],
        "panel_channel_id": str(body.channel_id),
        "panel_message_id": message["id"],
    })