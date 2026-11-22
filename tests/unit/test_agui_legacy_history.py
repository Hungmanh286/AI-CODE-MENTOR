"""History of sessions created before the AG-UI switch (BACKEND-PLAN GĐ4.1).

The legacy WebSocket graph stored, per question: HumanMessage ->
AIMessage(name="agent", tool_calls) -> ToolMessage(answer as JSON
``{"message": ...}`` or plain text, or an ``Error: ...`` on failure).
"""

import asyncio
import uuid

import httpx
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.api.agui import create_standalone_app
from app.services import agui_legacy_history
from app.services.agui_legacy_history import legacy_to_agui


def _legacy_turn(question, answer, *, status="success"):
    call_id = f"call_{uuid.uuid4().hex[:6]}"
    return [
        HumanMessage(content=question, id=str(uuid.uuid4())),
        AIMessage(content="", name="agent", id=str(uuid.uuid4()),
                  tool_calls=[{"id": call_id, "name": "answer_tool", "args": {"query": question}}]),
        ToolMessage(content=answer, tool_call_id=call_id, status=status, id=str(uuid.uuid4())),
    ]


def test_question_answer_pairs_become_user_and_assistant_text_with_stable_ids():
    messages = [*_legacy_turn("Biến là gì?", '{"message": "Biến lưu **giá trị**."}'),
                *_legacy_turn("Tóm tắt", "Tài liệu nói về OOP.")]
    out = legacy_to_agui("s1", messages)
    assert out == [
        {"id": "legacy-s1-0-u", "role": "user", "content": "Biến là gì?"},
        {"id": "legacy-s1-0-a", "role": "assistant", "content": "Biến lưu **giá trị**."},
        {"id": "legacy-s1-1-u", "role": "user", "content": "Tóm tắt"},
        {"id": "legacy-s1-1-a", "role": "assistant", "content": "Tài liệu nói về OOP."},
    ]
    assert legacy_to_agui("s1", messages) == out  # deterministic: the client echoes these ids


def test_failed_tool_answers_are_not_shown_as_assistant_messages():
    messages = [*_legacy_turn("hello", "Error: ConnectError('refused')", status="error"),
                *_legacy_turn("hello", "Error: timeout")]
    assert [m["role"] for m in legacy_to_agui("s1", messages)] == ["user", "user"]


def test_plain_ai_answer_without_tool_is_used():
    messages = [HumanMessage(content=[{"type": "text", "text": "hi"}], id="h"), AIMessage(content="Chào bạn", id="a")]
    assert legacy_to_agui("s2", messages) == [
        {"id": "legacy-s2-0-u", "role": "user", "content": "hi"},
        {"id": "legacy-s2-0-a", "role": "assistant", "content": "Chào bạn"},
    ]


def test_old_session_history_is_served_then_merged_without_duplicates(monkeypatch):
    session = str(uuid.uuid4())
    legacy = _legacy_turn("Biến là gì?", '{"message": "Biến lưu giá trị."}')

    async def fake_read(session_id):
        return legacy if session_id == session else []

    monkeypatch.setattr(agui_legacy_history, "read_legacy_messages", fake_read)
    app = create_standalone_app(legacy_history=agui_legacy_history.legacy_history)

    async def go():
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                before = (await client.get(f"/threads/{session}/messages")).json()
                body = {
                    "threadId": session, "runId": "run_1", "state": {}, "tools": [], "context": [],
                    "forwardedProps": {},
                    "messages": [*before["messages"], {"id": "u_new", "role": "user", "content": "xin chào"}],
                }
                r = await client.post("/agent", json=body, headers={"accept": "text/event-stream"})
                assert r.status_code == 200 and "RUN_FINISHED" in r.text
                after = (await client.get(f"/threads/{session}/messages")).json()
                fresh = (await client.get(f"/threads/{uuid.uuid4()}/messages")).json()
                return before, after, fresh

    before, after, fresh = asyncio.run(go())
    assert [m["id"] for m in before["messages"]] == [f"legacy-{session}-0-u", f"legacy-{session}-0-a"]
    ids = [m["id"] for m in after["messages"]]
    assert ids[:3] == [f"legacy-{session}-0-u", f"legacy-{session}-0-a", "u_new"]
    assert len(ids) == len(set(ids))
    assert fresh == {"messages": []}
