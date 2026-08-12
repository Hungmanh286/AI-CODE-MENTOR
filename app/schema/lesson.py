import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class Lesson(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    lesson_name: str = Field(index=True, nullable=False, unique=True)
    description: str = Field(sa_type=sa.Text(), nullable=False)
    content: str = Field(sa_type=sa.Text(), nullable=False)
    multiple_choice_exercises: str = Field(default=None, nullable=True)
    practice_exercises: str = Field(default=None, nullable=True)
