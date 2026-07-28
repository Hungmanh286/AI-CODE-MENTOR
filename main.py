"""Main entrypoint for the app."""

import warnings

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from scalar_fastapi import get_scalar_api_reference

from app.config import settings
from app.routes import Routers

warnings.simplefilter(action="ignore", category=UserWarning)
warnings.simplefilter(action="ignore", category=FutureWarning)


load_dotenv()


app = FastAPI(
    title="Chatbot service",
    openapi_url="/api/v1/openapi.json",
    description="API service for chatbot.",
    redoc_url=None,
)


app.add_middleware(GZipMiddleware, minimum_size=10000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/ping", include_in_schema=False)
async def health_check():
    return "pong"


@app.get("/apidocs", include_in_schema=False)
async def scalar_html():
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title=app.title,
        hide_models=True,
    )


app.include_router(Routers.chat_router, prefix="", tags=["Chatws"])
app.include_router(Routers.user_router, prefix="", tags=["User"])
app.include_router(Routers.progress_user_router, prefix="", tags=["ProgressUser"])
app.include_router(Routers.lesson_router, prefix="", tags=["Lesson"])
app.include_router(Routers.upload_pdf_router, prefix="", tags=["UploadPDF"])
app.include_router(Routers.process_data_router, prefix="", tags=["ProcessData"])
app.include_router(Routers.history_chat_router, prefix="", tags=["HistoryChat"])
app.include_router(Routers.notify_router, prefix="", tags=["Notify"])
app.include_router(Routers.auth_router, prefix="", tags=["Auth"])
app.include_router(Routers.mindmap_router, prefix="", tags=["MindMap"])
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8686, log_level="warning")
