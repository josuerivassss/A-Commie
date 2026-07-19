"""Autoroles configuration -- lives under `guilds.autoroles` in MongoDB,
matching the bot's `autoroles` cog exactly:
{"humans": [role_id, ...], "bots": [role_id, ...]}  -- max 2 each.

Role IDs are serialized as strings in every response: Discord snowflakes
are 64-bit integers, which exceed JavaScript's safe integer range and get
silently corrupted if sent as raw JSON numbers.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from core.access import require_access
from core.manager import mongo
from schemas.responses import HTTPResponse

router = APIRouter(
    prefix="/json/guilds/{guild_id}/autoroles", tags=["Autoroles"], dependencies=[Depends(require_access)]
)

MAX_ROLES_PER_KIND = 2


class AutorolesUpdate(BaseModel):
    humans: Optional[List[int]] = Field(default=None, max_length=MAX_ROLES_PER_KIND)
    bots: Optional[List[int]] = Field(default=None, max_length=MAX_ROLES_PER_KIND)


def _serialize(doc: dict) -> dict:
    # Cast every role ID to str before it leaves the API -- prevents JS
    # Number precision loss on the frontend for snowflakes >= 2^53.
    return {
        "humans": [str(r) for r in doc.get("humans", [])],
        "bots": [str(r) for r in doc.get("bots", [])],
    }


@router.get("")
async def get_autoroles(guild_id: int):
    doc = await mongo.get(table="guilds", id=guild_id, path="autoroles") or {}
    return HTTPResponse.use(data=_serialize(doc))


@router.patch("")
async def update_autoroles(guild_id: int, body: AutorolesUpdate):
    updates = body.model_dump(exclude_none=True)
    if not updates:
        return HTTPResponse.use(status=400, error="No fields provided to update")
    for field, value in updates.items():
        await mongo.set(table="guilds", id=guild_id, path=f"autoroles.{field}", value=value)
    doc = await mongo.get(table="guilds", id=guild_id, path="autoroles") or {}
    return HTTPResponse.use(data=_serialize(doc))