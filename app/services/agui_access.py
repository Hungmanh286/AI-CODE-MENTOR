"""Who may read/run an AG-UI thread (thread_id = session uuid)."""

from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from app.core.config import settings
from app.db.models.question import SessionProject

# user_id values the legacy /create-session stores when no user is known
_ANONYMOUS_OWNERS = {None, "", "default"}


def _engine() -> Engine:
    return settings._app_db_engine


def session_belongs_to_other_user(session_id: str, user_id: str) -> bool:
    """True when the session is registered (``/create-session``) to someone else.

    Sessions that are not registered yet (a brand-new chat) or registered
    without a user are accessible to any authenticated user.
    """
    with Session(_engine()) as db:
        owners = set(
            db.exec(select(SessionProject.user_id).where(SessionProject.session_id == session_id)).all()
        )
    owners -= _ANONYMOUS_OWNERS
    return bool(owners) and user_id not in owners
