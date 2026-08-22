"""Guild command/cog enable-disable toggle -- mirrors the bot's
`guilds.disabled` field (see bcommie/command_registry.py for the ID
scheme). This router never validates IDs against the registry itself
(that would duplicate it here); the dashboard cross-references IDs from
the public commands-data.json, and the bot's own check ignores unknown
IDs safely.
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from core.access import require_access
from core.manager import mongo
from schemas.responses import HTTPResponse

router = APIRouter(
    prefix="/json/guilds/{guild_id}/commands", tags=["Commands"], dependencies=[Depends(require_access)]
)

TOGGLE_ID_PATTERN = re.compile(r"^c?\d+(\.\d+)?$")


class ToggleRequest(BaseModel):
    id: str = Field(max_length=16)
    enabled: bool


@router.get("")
async def get_disabled_commands(guild_id: int):
    disabled = await mongo.get(table="guilds", id=guild_id, path="disabled") or []
    return HTTPResponse.use(data={"disabled": disabled})


@router.patch("/toggle")
async def toggle_command(guild_id: int, body: ToggleRequest):
    if not TOGGLE_ID_PATTERN.match(body.id):
        return HTTPResponse.use(status=400, error="Invalid command/cog ID")
    if body.enabled:
        await mongo.pull(table="guilds", id=guild_id, field="disabled", value=body.id)
    else:
        await mongo.push(table="guilds", id=guild_id, field="disabled", value=body.id, unique=True)
    disabled = await mongo.get(table="guilds", id=guild_id, path="disabled") or []
    return HTTPResponse.use(data={"disabled": disabled})

class ToggleManyRequest(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=64)
    enabled: bool

@router.patch("/toggle-many")
async def toggle_many_commands(guild_id: int, body: ToggleManyRequest):
    invalid = [i for i in body.ids if not TOGGLE_ID_PATTERN.match(i)]
    if invalid:
        return HTTPResponse.use(status=400, error=f"Invalid command/cog ID(s): {', '.join(invalid)}")
    if body.enabled:
        await mongo.pull_many(table="guilds", id=guild_id, field="disabled", values=body.ids)
    else:
        for target_id in body.ids:
            await mongo.push(table="guilds", id=guild_id, field="disabled", value=target_id)
    disabled = await mongo.get(table="guilds", id=guild_id, path="disabled") or []
    return HTTPResponse.use(data={"disabled": disabled})