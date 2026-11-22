"""GET /history-chat/{session_id} reads the legacy graph's checkpoint.

It used to read Langfuse ``/api/public/sessions/{id}``, which Langfuse removed on
2026-11-16 (410 Gone), so the endpoint always answered an error.
"""

import asyncio
import uuid

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.api.v1 import history
from app.services import agui_legacy_history


def _turn(question, answer):
    call_id = f"call_{uuid.uuid4().hex[:6]}"
    return [
        HumanMessage(content=question),
        AIMessage(content="", name="agent", tool_calls=[{"id": call_id, "name": "answer_tool", "args": {}}]),
        ToolMessage(content=answer, tool_call_id=call_id),
    ]


def _get(session_id):
    result = history.get_history_chat(session_id)
    return asyncio.run(result) if asyncio.iscoroutine(result) else result


def test_history_lists_question_answer_pairs_from_the_checkpoint(monkeypatch):
    async def read(session_id):
        assert session_id == "s1"
        return [*_turn("Biến là gì?", '{"message": "Biến lưu giá trị."}'), *_turn("Tóm tắt", "OOP.")]

    monkeypatch.setattr(agui_legacy_history, "read_legacy_messages", read)
    assert _get("s1") == {"history": [
        {"index": 1, "question": "Biến là gì?", "answer": "Biến lưu giá trị."},
        {"index": 2, "question": "Tóm tắt", "answer": "OOP."},
    ]}


def test_history_never_calls_langfuse(monkeypatch):
    async def read(session_id):
        return []

    monkeypatch.setattr(agui_legacy_history, "read_legacy_messages", read)
    monkeypatch.setattr("requests.get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    assert _get("s-empty") == {"history": []}
