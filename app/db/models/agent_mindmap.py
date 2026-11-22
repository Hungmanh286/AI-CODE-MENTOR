import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class AgentMindMap(SQLModel, table=True):
    """Mind map produced by the AG-UI agent: the ``show_mindmap`` tree as JSON.

    Separate from ``mindmaps`` (PNG images in MinIO read by the legacy Studio),
    so the legacy list never shows an entry it cannot render.
    """

    __tablename__ = "agent_mindmaps"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    session_id: str = Field(index=True)
    title: str
    tree_json: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
