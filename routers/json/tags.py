from fastapi import APIRouter, Depends
from core.exceptions import APIException
from core.manager import mongo
from core.security import require_api_key
from schemas.responses import HTTPResponse

router = APIRouter(prefix="/json/guilds/{guild_id}/tags", tags=["Tags"], dependencies=[Depends(require_api_key)])

@router.get(
    "",
    description="Lists every tag configured for a guild.",
    response_model=HTTPResponse,
)
async def list_tags(guild_id: int):
    tags = await mongo.get(table="tags", id=guild_id, path="tags")
    return HTTPResponse.use(data=tags or {})


@router.get(
    "/{tag_name}",
    description="Returns a single tag by its normalized name.",
    response_model=HTTPResponse,
)
async def get_tag(guild_id: int, tag_name: str):
    tag = await mongo.get(table="tags", id=guild_id, path=f"tags.{tag_name}")
    if tag is None:
        raise APIException(status=404, error=f"Tag '{tag_name}' not found")
    return HTTPResponse.use(data=tag)


@router.delete(
    "/{tag_name}",
    description="Deletes a tag by its normalized name.",
    response_model=HTTPResponse,
)
async def delete_tag(guild_id: int, tag_name: str):
    existing = await mongo.get(table="tags", id=guild_id, path=f"tags.{tag_name}")
    if existing is None:
        raise APIException(status=404, error=f"Tag '{tag_name}' not found")
    await mongo.delete_field(table="tags", id=guild_id, path=f"tags.{tag_name}")
    return HTTPResponse.use(data={"deleted": tag_name})
