import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class MindMap(SQLModel, table=True):
    __tablename__ = "mindmaps"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    session_id: str = Field(index=True)
    name: str
    source_path: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
