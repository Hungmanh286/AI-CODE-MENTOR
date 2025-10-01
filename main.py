"""Main entrypoint for the app."""

import warnings

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from scalar_fastapi import get_scalar_api_reference

from app.routes import Routers
from app.config import settings


warnings.simplefilter(action="ignore", category=UserWarning)
warnings.simplefilter(action="ignore", category=FutureWarning)


load_dotenv()


app = FastAPI(
    title="Chatbot service",
    openapi_url="/api/v1/openapi.json",
    description="API service for chatbot.",
    docs_url="/documentation",
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


app.mount("/docs", StaticFiles(directory="site", html=True), name="docs")


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8686, log_level="warning")
