"""AG-UI routes for the assistant-ui frontend (contract 4.3).

    POST /agent                   AG-UI run (text/event-stream), via ag-ui-langgraph
    GET  /agent/health            added by add_langgraph_fastapi_endpoint
    GET  /health                  {"ok": true}
    GET  /threads/{id}/messages   {"messages": AgUiMessage[], "state"?: {artifacts, jobs}}

``/agent`` is registered inside the lifespan (``agui_lifespan``): the Postgres
checkpointer only exists once the event loop runs.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any

import structlog
from ag_ui_langgraph import add_langgraph_fastapi_endpoint
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.encoders import jsonable_encoder
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from langgraph.checkpoint.memory import InMemorySaver

from app.agents.mentor_agui import build_graph, get_thread_messages, make_agent
from app.api.cors import install_cors
from app.core.config import settings
from app.core.security import verify_access_token
from app.services.agui_access import session_belongs_to_other_user

logger = structlog.get_logger(__name__)

AGENT_PATH = "/agent"

router = APIRouter()


async def _thread_id_of(request: Request) -> str | None:
    thread_id = request.path_params.get("thread_id")
    if thread_id is not None:
        return thread_id
    try:  # POST /agent: RunAgentInput.threadId (body is cached for the endpoint)
        body = json.loads(await request.body())
    except ValueError:
        return None  # malformed body: the endpoint answers 400
    value = body.get("threadId") if isinstance(body, dict) else None
    return value if isinstance(value, str) else None


async def require_agent_access(request: Request) -> None:
    """Bearer JWT + session ownership, when ``AGENT_AUTH_REQUIRED`` is on.

    The ``user`` entry of RunAgentInput.context is client-supplied and never
    used here.
    """
    if not settings.AGENT_AUTH_REQUIRED:
        return
    scheme, _, token = (request.headers.get("authorization") or "").partition(" ")
    payload = verify_access_token(token) if scheme.lower() == "bearer" and token else None
    user_id = payload.get("user_id") if isinstance(payload, dict) else None
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    thread_id = await _thread_id_of(request)
    if thread_id and await run_in_threadpool(session_belongs_to_other_user, thread_id, str(user_id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Session not accessible")


@router.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True}


def _graph(request: Request) -> Any:
    graph = getattr(request.app.state, "agui_graph", None)
    if graph is None:
        raise HTTPException(status_code=503, detail="agent not ready")
    return graph


@router.get("/threads/{thread_id}/messages", dependencies=[Depends(require_agent_access)])
async def thread_messages(thread_id: str, request: Request):
    return await get_thread_messages(_graph(request), thread_id)


async def _agent_body_400(request: Request, exc: RequestValidationError):
    # Contract 4.3: a malformed /agent body is rejected (400 or 422) before
    # any stream opens. Every other route keeps FastAPI's 422.
    if request.url.path == AGENT_PATH:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid RunAgentInput", "detail": jsonable_encoder(exc.errors()[:5])},
        )
    return await request_validation_exception_handler(request, exc)


def register_agui_error_handler(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _agent_body_400)


def install_agent(app: FastAPI, graph: Any) -> None:
    app.state.agui_graph = graph
    add_langgraph_fastapi_endpoint(
        app=app,
        agent=make_agent(graph),
        path=AGENT_PATH,
        dependencies=[Depends(require_agent_access)],
    )


CheckpointerFactory = Callable[[], AbstractAsyncContextManager[Any]]


@asynccontextmanager
async def agui_lifespan(app: FastAPI, checkpointer: CheckpointerFactory) -> AsyncIterator[None]:
    async with checkpointer() as saver:
        install_agent(app, build_graph(checkpointer=saver))
        yield


@asynccontextmanager
async def _in_memory() -> AsyncIterator[InMemorySaver]:
    yield InMemorySaver()


def create_standalone_app() -> FastAPI:
    """AG-UI routes only, in-memory checkpointer: for scripts/agui_selfcheck.py.

    Same CORS and error handling as ``main.app``; the LLM hooks stay unset, so
    graph nodes use their deterministic placeholders.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with agui_lifespan(app, _in_memory):
            yield

    app = FastAPI(title="Mentor AG-UI agent (standalone)", lifespan=lifespan)
    install_cors(app)
    register_agui_error_handler(app)
    app.include_router(router)
    return app
