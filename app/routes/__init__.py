from .chat import router as chat_router
from .user import router as user_router
from .progress_user import router as progress_user_router
from .lesson import router as lesson_router


class Routers:
    chat_router = chat_router
    user_router = user_router
    progress_user_router = progress_user_router
    lesson_router = lesson_router


__all__ = ["Routers"]
