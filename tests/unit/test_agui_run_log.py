"""One summary log record per AG-UI run (BACKEND-PLAN GĐ4.4)."""

import asyncio
import uuid

import httpx
from structlog.testing import capture_logs

from app.api.agui import create_standalone_app


def _post(text: str):
    app = create_standalone_app()
    thread = str(uuid.uuid4())
    body = {
        "threadId": thread, "runId": f"run_{uuid.uuid4().hex}", "state": {}, "tools": [],
        "context": [], "forwardedProps": {},
        "messages": [{"id": f"u_{uuid.uuid4().hex}", "role": "user", "content": text}],
    }

    async def go():
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                await client.post("/agent", json=body, headers={"accept": "text/event-stream"})

    with capture_logs() as logs:
        asyncio.run(go())
    return thread, body["runId"], [e for e in logs if e.get("event") == "agui run"]


def test_each_run_logs_thread_run_nodes_duration_and_outcome():
    thread, run_id, records = _post("vẽ mindmap OOP")
    assert len(records) == 1
    rec = records[0]
    assert rec["thread_id"] == thread and rec["run_id"] == run_id
    assert rec["nodes"] == ["router", "mindmap"]
    assert rec["end"] == "RUN_FINISHED" and rec["error_code"] is None and rec["interrupted"] is False
    assert rec["duration_ms"] >= 0


def test_interrupted_run_is_marked():
    _, _, records = _post("tạo quiz")
    assert records[0]["interrupted"] is True and records[0]["nodes"] == ["router", "quiz_intro", "quiz"]


def test_agent_stream_disables_proxy_buffering():
    app = create_standalone_app()
    body = {
        "threadId": str(uuid.uuid4()), "runId": "run_x", "state": {}, "tools": [], "context": [],
        "forwardedProps": {}, "messages": [{"id": "u1", "role": "user", "content": "xin chào"}],
    }

    async def go():
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                agent = await client.post("/agent", json=body, headers={"accept": "text/event-stream"})
                health = await client.get("/health")
                return agent, health

    agent, health = asyncio.run(go())
    assert agent.headers.get("x-accel-buffering") == "no"
    assert agent.headers.get("cache-control") == "no-cache"
    assert "x-accel-buffering" not in health.headers
