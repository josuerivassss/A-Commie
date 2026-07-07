from fastapi import APIRouter, Depends
from core.exceptions import APIException
from core.manager import postgres
from core.security import require_api_key
from schemas.responses import HTTPResponse

router = APIRouter(prefix="/json", tags=["Reminders"], dependencies=[Depends(require_api_key)])


@router.get(
    "/users/{user_id}/reminders",
    description="Lists all pending reminders for a user.",
    response_model=HTTPResponse,
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
async def delete_reminder(reminder_id: int):
    existing = await postgres.find(table="reminders", where={"id": reminder_id}, limit=1)
    if not existing:
        raise APIException(status=404, error=f"Reminder '{reminder_id}' not found")
    await postgres.delete(table="reminders", id=reminder_id)
    return HTTPResponse.use(data={"deleted": reminder_id})
