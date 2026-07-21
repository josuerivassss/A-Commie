"""Embed builder & sender: constructs up-to-10-embed Discord messages from
the dashboard, sends them via the bot token, and optionally seeds reactions
on the resulting message. Rate-limited server-wide (see core/embed_cooldown.py).
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends

from core.access import require_access
from core.discord_oauth import DiscordOAuthError, discord_oauth
from core.embed_cooldown import mark_sent, seconds_remaining
from core.exceptions import APIException
from schemas.responses import HTTPResponse

import re
from pydantic import BaseModel, Field, field_validator, model_validator

router = APIRouter(prefix="/json/guilds/{guild_id}/embeds", tags=["Embeds"], dependencies=[Depends(require_access)])

MAX_EMBEDS = 10
MAX_TOTAL_CHARACTERS = 6000
MAX_REACTIONS = 20
CUSTOM_EMOJI_PATTERN = re.compile(r"^<a?:(\w+):(\d+)>$")
URL_PATTERN = re.compile(r"^https?://\S+$")


def _validate_url(value: str | None) -> str | None:
    if not value:
        return value
    if not URL_PATTERN.match(value):
        raise ValueError("Must be a valid http(s) URL")
    return value

class EmbedField(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    value: str = Field(min_length=1, max_length=1024)
    inline: bool = False

class EmbedAuthor(BaseModel):
    name: Optional[str] = Field(default=None, max_length=256)
    url: Optional[str] = None
    icon_url: Optional[str] = None

    @field_validator("url", "icon_url")
    @classmethod
    def _check_urls(cls, value: Optional[str]) -> Optional[str]:
        return _validate_url(value)


class EmbedFooter(BaseModel):
    text: Optional[str] = Field(default=None, max_length=2048)
    icon_url: Optional[str] = None

    @field_validator("icon_url")
    @classmethod
    def _check_url(cls, value: Optional[str]) -> Optional[str]:
        return _validate_url(value)

class EmbedPayload(BaseModel):
    title: Optional[str] = Field(default=None, max_length=256)
    description: Optional[str] = Field(default=None, max_length=4096)
    url: Optional[str] = None
    color: Optional[int] = Field(default=None, ge=0, le=0xFFFFFF)
    timestamp: Optional[str] = None
    footer: Optional[EmbedFooter] = None
    image: Optional[str] = None
    thumbnail: Optional[str] = None
    author: Optional[EmbedAuthor] = None
    fields: list[EmbedField] = Field(default_factory=list, max_length=25)

    @field_validator("url", "image", "thumbnail")
    @classmethod
    def _check_urls(cls, value: Optional[str]) -> Optional[str]:
        return _validate_url(value)

    def character_count(self) -> int:
        total = len(self.title or "") + len(self.description or "")
        if self.footer:
            total += len(self.footer.text or "")
        if self.author:
            total += len(self.author.name or "")
        for field in self.fields:
            total += len(field.name) + len(field.value)
        return total

    def to_discord_dict(self) -> dict:
        payload: dict = {}
        if self.title:
            payload["title"] = self.title
        if self.description:
            payload["description"] = self.description
        if self.url:
            payload["url"] = self.url
        if self.color is not None:
            payload["color"] = self.color
        if self.timestamp:
            payload["timestamp"] = self.timestamp
        if self.footer and (self.footer.text or self.footer.icon_url):
            payload["footer"] = {k: v for k, v in self.footer.model_dump().items() if v}
        if self.image:
            payload["image"] = {"url": self.image}
        if self.thumbnail:
            payload["thumbnail"] = {"url": self.thumbnail}
        if self.author and (self.author.name or self.author.url or self.author.icon_url):
            payload["author"] = {k: v for k, v in self.author.model_dump().items() if v}
        if self.fields:
            payload["fields"] = [f.model_dump() for f in self.fields]
        return payload


class SendEmbedRequest(BaseModel):
    channel_id: int
    content: Optional[str] = Field(default=None, max_length=2000)
    embeds: list[EmbedPayload] = Field(min_length=1, max_length=MAX_EMBEDS)
    reactions: list[str] = Field(default_factory=list, max_length=MAX_REACTIONS)

    @model_validator(mode="after")
    def _check_total_characters(self) -> "SendEmbedRequest":
        total = sum(e.character_count() for e in self.embeds)
        if total > MAX_TOTAL_CHARACTERS:
            raise ValueError(f"Combined embed content exceeds Discord's {MAX_TOTAL_CHARACTERS}-character limit")
        return self


def _normalize_reaction(raw: str) -> str:
    """Converts `<:name:id>` / `<a:name:id>` to Discord's REST reaction
    path segment (`name:id`); standard unicode emoji pass through as-is."""
    match = CUSTOM_EMOJI_PATTERN.match(raw)
    return f"{match.group(1)}:{match.group(2)}" if match else raw


@router.get(
    "/channels",
    description="Lists the guild's text channels annotated with whether the bot can post embeds there.",
    response_model=HTTPResponse,
)
async def get_sendable_channels(guild_id: int):
    channels = await discord_oauth.get_sendable_text_channels(guild_id)
    return HTTPResponse.use(data=channels)


@router.get(
    "/cooldown",
    description="Seconds remaining before this guild can send another dashboard embed (0 if ready now).",
    response_model=HTTPResponse,
)
async def get_cooldown(guild_id: int):
    return HTTPResponse.use(data={"seconds_remaining": seconds_remaining(guild_id)})


@router.post(
    "/send",
    description="Sends a multi-embed message (with optional reactions) to a channel via the bot.",
    response_model=HTTPResponse,
)
async def send_embed(guild_id: int, body: SendEmbedRequest):
    remaining = seconds_remaining(guild_id)
    if remaining > 0:
        raise APIException(status=429, error="embed_cooldown_active", data={"seconds_remaining": remaining})

    channels = await discord_oauth.get_sendable_text_channels(guild_id)
    target = next((c for c in channels if int(c["id"]) == body.channel_id), None)
    if target is None:
        raise APIException(status=404, error="Channel not found in this server")
    if not target["can_send"]:
        raise APIException(status=403, error="The bot cannot send embeds in that channel")

    try:
        message = await discord_oauth.send_message(
            body.channel_id, content=body.content, embeds=[e.to_discord_dict() for e in body.embeds]
        )
    except DiscordOAuthError as exc:
        raise APIException(status=502, error=f"Discord rejected the message: {exc}") from None

    mark_sent(guild_id)

    failed_reactions = []
    for index, raw_emoji in enumerate(body.reactions):
        ok = await discord_oauth.add_reaction(body.channel_id, message["id"], _normalize_reaction(raw_emoji))
        if not ok:
            failed_reactions.append(raw_emoji)
        if index < len(body.reactions) - 1:
            await asyncio.sleep(0.35)  # stay under Discord's reaction-route rate limit

    return HTTPResponse.use(
        data={"message_id": message["id"], "channel_id": body.channel_id, "failed_reactions": failed_reactions}
    )