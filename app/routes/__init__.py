from .chat import router as chat_router
from .user import router as user_router
from .progress_user import router as progress_user_router
from .lesson import router as lesson_router
from .upload_pdf import router as upload_pdf_router
from .process_data import router as process_data_router
from .history_chat import router as history_chat_router


class Routers:
    chat_router = chat_router
    user_router = user_router
    progress_user_router = progress_user_router
    lesson_router = lesson_router
    upload_pdf_router = upload_pdf_router
    process_data_router = process_data_router
    history_chat_router = history_chat_router


__all__ = ["Routers"]
