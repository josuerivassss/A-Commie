"""Starboard configuration -- lives in MongoDB (`starboard_config`), same
collection the bot's `starboard` cog reads/writes directly.
"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from core.access import require_access
from core.manager import mongo
from schemas.responses import HTTPResponse

router = APIRouter(
    prefix="/json/guilds/{guild_id}/starboard", tags=["Starboard"], dependencies=[Depends(require_access)]
)


class StarboardUpdate(BaseModel):
    enabled: Optional[bool] = None
    channel_id: Optional[int] = None
    emoji: Optional[str] = Field(default=None, max_length=60)
    threshold: Optional[int] = Field(default=None, ge=1, le=500)
    count_self_stars: Optional[bool] = None


@router.get("")
async def get_starboard(guild_id: int):
    doc = await mongo.get(table="starboard_config", id=guild_id) or {}
    return HTTPResponse.use(data=doc)


@router.patch("")
async def update_starboard(guild_id: int, body: StarboardUpdate):
    updates = body.model_dump(exclude_none=True)
    if not updates:
        return HTTPResponse.use(status=400, error="No fields provided to update")
    await mongo.set(table="starboard_config", id=guild_id, data=updates, upsert=True)
    doc = await mongo.get(table="starboard_config", id=guild_id) or {}
    return HTTPResponse.use(data=doc)