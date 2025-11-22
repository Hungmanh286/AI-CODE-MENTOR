from typing import Optional, List
from sqlmodel import Field, SQLModel, Relationship
from datetime import datetime
import uuid


class Project(SQLModel, table=True):
    __tablename__ = "projects"
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    session_id: str
    name: str
    source_path: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    questions: List["Question"] = Relationship(back_populates="project")


class Question(SQLModel, table=True):
    __tablename__ = "questions"
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    project_id: Optional[str] = Field(default=None, foreign_key="projects.id")
    question_id: str
    question: str
    type: str
    difficulty: Optional[str] = None
    correct_answer: Optional[int] = None
    explanation: Optional[str] = None
    answer: Optional[int] = None
    score: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    project: Optional[Project] = Relationship(back_populates="questions")
    options: List["QuestionOption"] = Relationship(back_populates="question")


class QuestionOption(SQLModel, table=True):
    __tablename__ = "question_options"
    id: Optional[int] = Field(default=None, primary_key=True)
    question_id: str = Field(foreign_key="questions.id")
    option_index: int
    option_text: str

    question: Optional[Question] = Relationship(back_populates="options")


class SessionProject(SQLModel, table=True):
    __tablename__ = "session_projects"
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str
    session_name: str
    project_id: Optional[str] = Field(default=None)
