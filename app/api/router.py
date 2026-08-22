"""Single place where every router is mounted onto the application."""

from fastapi import APIRouter

from app.api.v1 import (
    auth,
    history,
    lesson,
    mindmap,
    notify,
    process_data,
    progress,
    upload,
    user,
)
from app.api.ws import chat

api_router = APIRouter()

api_router.include_router(chat.router, tags=["Chatws"])
api_router.include_router(user.router, tags=["User"])
api_router.include_router(progress.router, tags=["ProgressUser"])
api_router.include_router(lesson.router, tags=["Lesson"])
api_router.include_router(upload.router, tags=["UploadPDF"])
api_router.include_router(process_data.router, tags=["ProcessData"])
api_router.include_router(history.router, tags=["HistoryChat"])
api_router.include_router(notify.router, tags=["Notify"])
api_router.include_router(auth.router, tags=["Auth"])
api_router.include_router(mindmap.router, tags=["MindMap"])

__all__ = ["api_router"]
