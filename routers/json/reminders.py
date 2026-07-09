from fastapi import APIRouter, Depends
from core.access import require_access, require_self_or_api_key, resolve_identity
from core.discord_oauth import discord_oauth
from core.exceptions import APIException
from core.manager import postgres
from schemas.responses import HTTPResponse

router = APIRouter(prefix="/json", tags=["Reminders"])


@router.get(
    "/users/{user_id}/reminders",
    description="Lists all pending reminders for a user.",
    response_model=HTTPResponse,
    dependencies=[Depends(require_self_or_api_key)],
)
async def list_user_reminders(user_id: int):
    rows = await postgres.find(
        table="reminders", where={"user_id": user_id, "reminded": False}, order_by="remind_at ASC"
    )
    return HTTPResponse.use(data=rows)


@router.get(
    "/guilds/{guild_id}/reminders",
    description="Lists all pending reminders created in a guild.",
    response_model=HTTPResponse,
    dependencies=[Depends(require_access)],
)
async def list_guild_reminders(guild_id: int):
    rows = await postgres.find(
        table="reminders", where={"guild_id": guild_id, "reminded": False}, order_by="remind_at ASC"
    )
    return HTTPResponse.use(data=rows)


@router.delete(
    "/reminders/{reminder_id}",
    description="Cancels (deletes) a reminder by its id.",
    response_model=HTTPResponse,
)
async def delete_reminder(reminder_id: int, identity: dict | None = Depends(resolve_identity)):
    existing = await postgres.find(table="reminders", where={"id": reminder_id}, limit=1)
    if not existing:
        raise APIException(status=404, error=f"Reminder '{reminder_id}' not found")
    reminder = existing[0]

    if identity is not None:
        is_owner = int(identity["sub"]) == reminder["user_id"]
        manages_guild = False
        if not is_owner and reminder.get("guild_id"):
            manageable = await discord_oauth.get_user_manageable_guilds(identity["discord_token"])
            manages_guild = any(int(g["id"]) == reminder["guild_id"] for g in manageable)
        if not (is_owner or manages_guild):
            raise APIException(status=403, error="You cannot manage that reminder")

    await postgres.delete(table="reminders", id=reminder_id)
    return HTTPResponse.use(data={"deleted": reminder_id})