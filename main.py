"""Main entrypoint for the app."""

import warnings
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from scalar_fastapi import get_scalar_api_reference

from app.agents.mentor_agui.backends import default_backend
from app.api.agui import NoBufferingForAgentStream, agui_lifespan, register_agui_error_handler
from app.api.cors import install_cors
from app.api.router import api_router
from app.core.config import settings
from app.infra.agui_checkpointer import agui_checkpointer
from app.services.agui_legacy_history import legacy_history

warnings.simplefilter(action="ignore", category=UserWarning)
warnings.simplefilter(action="ignore", category=FutureWarning)


load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables, then serve the AG-UI agent (POST /agent)."""
    # Importing app.db.base registers every model with SQLModel metadata.
    from app.db.base import SQLModel

    SQLModel.metadata.create_all(settings._app_db_engine)
    async with agui_lifespan(
        app, agui_checkpointer, backend=default_backend(), legacy_history=legacy_history
    ):
        yield


app = FastAPI(
    title="Chatbot service",
    lifespan=lifespan,
    openapi_url="/api/v1/openapi.json",
    description="API service for chatbot.",
    redoc_url=None,
)


app.add_middleware(GZipMiddleware, minimum_size=10000)
app.add_middleware(NoBufferingForAgentStream)
install_cors(app)
register_agui_error_handler(app)


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


app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8686, log_level="warning")
