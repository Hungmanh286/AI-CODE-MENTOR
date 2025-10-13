from typing import Optional
from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_name: str = Field(index=True, nullable=False, unique=True)
    email: Optional[str] = Field(default=None, index=True, nullable=True)
    full_name: Optional[str] = Field(default=None, nullable=True)
    hashed_password: str = Field(nullable=False)


class ProgressUser(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    lesson_id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, nullable=False)
    user_name: str = Field(index=True, nullable=False)
    lesson_name: str = Field(index=True, nullable=False)
    progress: float = Field(default=0.0, nullable=False)
