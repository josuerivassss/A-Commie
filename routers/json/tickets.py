"""Ticket system configuration and panel publishing -- mirrors the bot's
`guilds.tickets` document (bcommie/cogs/tickets.py) exactly, so config
written here is read directly by the bot with no translation layer.

The dashboard can also publish the ticket-opening panel (an embed + button)
directly via the bot token. Discord routes the resulting button click to
the bot process regardless of which process sent the original message, as
long as the bot has TicketPanelView registered (it always does, via
cog_load), so a dashboard-posted panel works identically to one posted
with `!ticket panel`.
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

router = APIRouter(prefix="/json/guilds/{guild_id}/tickets", tags=["Tickets"], dependencies=[Depends(require_access)])

DEFAULT_TICKETS = {
    "enabled": False,
    "parent_channel_id": None,
    "staff_role_id": None,
    "welcome_message": "Welcome {user.mention}! Support will be with you shortly.",
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
PANEL_BUTTON_LABEL = "Open Ticket"
PANEL_BUTTON_EMOJI = "\U0001f3ab"
PANEL_COLOR = 0x992D22  # discord.Colour.dark_red(), matches the bot's own !ticket panel command


class TicketsUpdate(BaseModel):
    enabled: Optional[bool] = None
    parent_channel_id: Optional[int] = None
    staff_role_id: Optional[int] = None
    welcome_message: Optional[str] = Field(default=None, min_length=MIN_MESSAGE_LENGTH, max_length=MAX_MESSAGE_LENGTH)


class PostPanelRequest(BaseModel):
    channel_id: int


def _serialize(doc: dict) -> dict:
    merged = {**DEFAULT_TICKETS, **doc}
    merged["parent_channel_id"] = str(merged["parent_channel_id"]) if merged["parent_channel_id"] is not None else None
    merged["staff_role_id"] = str(merged["staff_role_id"]) if merged["staff_role_id"] is not None else None
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

    if "parent_channel_id" in updates:
        channels = await discord_oauth.get_ticket_channels(guild_id)
        target = next((c for c in channels if int(c["id"]) == updates["parent_channel_id"]), None)
        if target is None:
            raise APIException(status=404, error="Channel not found in this server")
        if not target["can_host_tickets"]:
            raise APIException(
                status=403,
                error="The bot needs View Channel, Create Private Threads, and Send Messages in Threads there",
            )

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
    doc = await mongo.get(table="guilds", id=guild_id, path="tickets") or {}
    config = {**DEFAULT_TICKETS, **doc}
    if not config["parent_channel_id"]:
        raise APIException(status=400, error="Set and save a parent channel before publishing the panel")

    channels = await discord_oauth.get_ticket_channels(guild_id)
    target = next((c for c in channels if int(c["id"]) == body.channel_id), None)
    if target is None:
        raise APIException(status=404, error="Channel not found in this server")
    if not target["can_send_panel"]:
        raise APIException(status=403, error="The bot cannot send messages/embeds in that channel")

    language = await mongo.get(table="guilds", id=guild_id, path="language") or "en"
    text = PANEL_TEXT.get(language, PANEL_TEXT["en"])
    embed = {"title": text["title"], "description": text["description"], "color": PANEL_COLOR}
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

    await mongo.set(table="guilds", id=guild_id, path="tickets.enabled", value=True)
    return HTTPResponse.use(data={"message_id": message["id"], "channel_id": body.channel_id})