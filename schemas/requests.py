from typing import Optional
from pydantic import BaseModel, Field
 
class FraseCreate(BaseModel):
    text: str
    author: str

class GuildConfigUpdate(BaseModel):
    """Partial update for a guild's configuration document (`guilds` collection).
    Only the fields provided are changed; omitted fields are left untouched.
    """
    prefix: Optional[str] = Field(default=None, max_length=10)
    language: Optional[str] = Field(default=None, max_length=5)
    welcome_enabled: Optional[bool] = None
    welcome_channel_id: Optional[int] = None
    welcome_message: Optional[str] = None
    leave_enabled: Optional[bool] = None
    leave_channel_id: Optional[int] = None
    leave_message: Optional[str] = None
