from typing import Optional
from pydantic import BaseModel
 
class FraseCreate(BaseModel):
    text: str
    author: str