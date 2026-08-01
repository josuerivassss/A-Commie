from typing import Optional
from pydantic import BaseModel, Field

SNOWFLAKE_MIN = 4194304
SNOWFLAKE_MAX = 9223372036854775807

class FraseCreate(BaseModel):
    text: str
    author: str

class GuildConfigUpdate(BaseModel):
    prefix: Optional[str] = Field(default=None, max_length=10)
    nickname: Optional[str] = Field(default=None, max_length=32)
    language: Optional[str] = Field(default=None, max_length=5)
    welcome_enabled: Optional[bool] = None
    welcome_channel_id: Optional[int] = Field(default=None, ge=SNOWFLAKE_MIN, le=SNOWFLAKE_MAX)
    welcome_message: Optional[str] = None
    leave_enabled: Optional[bool] = None
    leave_channel_id: Optional[int] = Field(default=None, ge=SNOWFLAKE_MIN, le=SNOWFLAKE_MAX)
    leave_message: Optional[str] = None