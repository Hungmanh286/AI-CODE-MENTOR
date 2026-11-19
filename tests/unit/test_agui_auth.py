"""Access control of the AG-UI routes (BACKEND-PLAN GĐ1.6 / GĐ4.2).

Off by default (the frontend does not send Authorization yet). When
``AGENT_AUTH_REQUIRED`` is on: Bearer JWT required, and a session that is
registered to another user is refused. The ``user`` context sent by the client
is never used for authorization.
"""

import asyncio
import json
import uuid

import httpx
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings
from app.core.security import create_access_token
from app.db.models.question import SessionProject


def _token(user_id: str) -> str:
    return create_access_token({"user_id": user_id, "username": user_id, "token_limit": 1000})


def _run_body(thread_id: str) -> dict:
    return {
        "threadId": thread_id,
        "runId": f"run_{uuid.uuid4().hex}",
        "state": {},
        "messages": [{"id": f"u_{uuid.uuid4().hex}", "role": "user", "content": "xin chào"}],
        "tools": [],
        "context": [{"description": "user", "value": json.dumps({"user_id": "owner"})}],
        "forwardedProps": {},
    }


@pytest.fixture
def owned_session(monkeypatch):
    """A session registered to user 'owner' in an in-memory app DB."""
    from app.services import agui_access

    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine, tables=[SessionProject.__table__])
    session_id = str(uuid.uuid4())
    with Session(engine) as db:
        db.add(SessionProject(session_id=session_id, user_id="owner", session_name="s"))
        db.commit()
    monkeypatch.setattr(agui_access, "_engine", lambda: engine)
    return session_id


def _call(method: str, path: str, **kwargs) -> httpx.Response:
    from app.api.agui import create_standalone_app

    app = create_standalone_app()

    async def go():
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.request(method, path, **kwargs)

    return asyncio.run(go())


def test_auth_off_by_default_allows_requests_without_token(owned_session):
    assert settings.AGENT_AUTH_REQUIRED is False
    r = _call("GET", f"/threads/{owned_session}/messages")
    assert r.status_code == 200


def test_auth_on_rejects_missing_token(monkeypatch, owned_session):
    monkeypatch.setattr(settings, "AGENT_AUTH_REQUIRED", True)
    assert _call("GET", f"/threads/{owned_session}/messages").status_code == 401
    assert _call("POST", "/agent", json=_run_body(owned_session)).status_code == 401


def test_auth_on_rejects_invalid_token(monkeypatch, owned_session):
    monkeypatch.setattr(settings, "AGENT_AUTH_REQUIRED", True)
    r = _call("GET", f"/threads/{owned_session}/messages", headers={"authorization": "Bearer nope"})
    assert r.status_code == 401


def test_auth_on_rejects_session_of_another_user(monkeypatch, owned_session):
    monkeypatch.setattr(settings, "AGENT_AUTH_REQUIRED", True)
    headers = {"authorization": f"Bearer {_token('intruder')}"}
    assert _call("GET", f"/threads/{owned_session}/messages", headers=headers).status_code == 403
    # the client-sent "user" context claims "owner": it must not grant access
    r = _call("POST", "/agent", json=_run_body(owned_session), headers=headers)
    assert r.status_code == 403


def test_auth_on_allows_owner_and_unregistered_session(monkeypatch, owned_session):
    monkeypatch.setattr(settings, "AGENT_AUTH_REQUIRED", True)
    headers = {"authorization": f"Bearer {_token('owner')}", "accept": "text/event-stream"}
    assert _call("GET", f"/threads/{owned_session}/messages", headers=headers).status_code == 200
    r = _call("POST", "/agent", json=_run_body(owned_session), headers=headers)
    assert r.status_code == 200 and "RUN_FINISHED" in r.text
    fresh = str(uuid.uuid4())  # new chat not yet registered via /create-session
    assert _call("GET", f"/threads/{fresh}/messages", headers=headers).status_code == 200
