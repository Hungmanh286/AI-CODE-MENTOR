"""CORS for the whole API (REST, AG-UI, SSE).

Contract 4.3 of the AG-UI frontend needs ``Access-Control-Allow-Origin: *`` and
``Access-Control-Allow-Headers`` covering ``content-type, authorization,
accept``. Starlette only answers ``*`` when credentials are disabled (with
credentials it echoes the request origin). No client sends cookies or uses
``credentials: "include"``, so credentials stay off. With ``allow_headers=["*"]``
Starlette mirrors the requested headers, ``authorization`` included.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings


def install_cors(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS or ["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
