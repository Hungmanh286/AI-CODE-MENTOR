from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class HealthCheck(BaseModel):
    healthy: bool = Field(..., json_schema_extra={"example": True})


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None
    scopes: List[str] = []


class UserGroup(str, Enum):
    default = "default"
    basic = "basic"
    standard = "standard"
    pro = "pro"
    unlimited = "unlimited"


class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None
    priority: Optional[int] = None
    group: Optional[UserGroup] = UserGroup.default


class UserInDB(User):
    hashed_password: str


class UserToken(BaseModel):
    """User decode info"""

    user_id: str = Field(..., description="user id")
    username: str = Field(..., description="user name")
    token_limit: int = Field(
        10000,
        description="Usage OpenAI token limit, see https://platform.openai.com/tokenizer",
    )
