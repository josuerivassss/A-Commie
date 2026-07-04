import json
import typing
import pydantic
from fastapi.responses import JSONResponse


class PrettyJSONResponse(JSONResponse):
    def render(self, content: typing.Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=4,
            separators=(", ", ": ")
        ).encode("utf-8")


class HTTPResponse(pydantic.BaseModel):
    status: int
    data: typing.Any
    success: bool

    @staticmethod
    def use(
        *,
        status: int = 200,
        data: str | int | float | dict | list | None = None,
        error: str | None = None,
        headers: typing.Dict[str, str] | None = None
    ) -> PrettyJSONResponse:
        return PrettyJSONResponse(
            content={
                "status": status,
                "data": data,
                "error": error,
                "success": status in (200, 201),
            },
            status_code=status,
            headers=headers,
        )

    @staticmethod
    def fail(status: int = 400, error: str = "Bad request", data=None) -> None:
        from core.exceptions import APIException
        raise APIException(status=status, error=error, data=data)

class TagOut(pydantic.BaseModel):
    name: str
    content: str
    author: int
    created_at: int


class ReminderOut(pydantic.BaseModel):
    id: int
    user_id: int
    guild_id: int | None
    channel_id: int | None
    message: str
    remind_at: str
    reminded: bool


class AuditLogEntryOut(pydantic.BaseModel):
    id: int
    actor_id: int
    guild_id: int | None
    action: str
    target_id: int | None
    details: str
    created_at: str
