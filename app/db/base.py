"""Import every model so ``SQLModel.metadata`` is complete.

Import this module (never the individual models) before calling
``SQLModel.metadata.create_all`` or generating migrations.
"""

from sqlmodel import SQLModel

from app.db.models.lesson import Lesson  # noqa: F401
from app.db.models.mindmap import MindMap  # noqa: F401
from app.db.models.question import (  # noqa: F401
    Project,
    Question,
    QuestionOption,
    SessionProject,
)
from app.db.models.upload import UploadFileStatus  # noqa: F401
from app.db.models.user import ProgressUser, User  # noqa: F401

metadata = SQLModel.metadata

__all__ = ["metadata", "SQLModel"]
