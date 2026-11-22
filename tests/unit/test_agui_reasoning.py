"""Reasoning ("đang suy nghĩ") of the answer model reaches the client and survives F5.

The answer model runs on OpenRouter with ``reasoning={...}``: ChatOpenRouter puts
the reasoning text in ``additional_kwargs["reasoning_content"]`` of the stream
chunks, without any id. ag-ui-langgraph streams it as REASONING_* under a random
id, while history/snapshots name it after the stored reasoning block, so without
a shared id the client renders the reasoning twice (frontend README 9.7).
"""

import asyncio
import json
import uuid

import httpx
import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

from app.agents.mentor_agui.reasoning import StableReasoningIds
from app.api.agui import create_standalone_app

THOUGHT = ["Người học hỏi về đa hình. ", "Mình sẽ giải thích ngắn kèm ví dụ."]
ANSWER = ["Đa hình là ", "khả năng một lời gọi chạy nhiều cách."]


class FakeOpenRouterStream(BaseChatModel):
    """Streams like ChatOpenRouter with reasoning on: reasoning chunks first, then text."""

    @property
    def _llm_type(self) -> str:
        return "fake-openrouter"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        text = "".join(ANSWER)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text, id="gen-1"))])

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
        gen_id = f"gen-{uuid.uuid4().hex[:8]}"  # OpenRouter: one id per generation
        for piece in THOUGHT:
            yield ChatGenerationChunk(message=AIMessageChunk(
                content="", id=gen_id, additional_kwargs={"reasoning_content": piece}))
        for piece in ANSWER:
            yield ChatGenerationChunk(message=AIMessageChunk(content=piece, id=gen_id))


class ReasoningModel(StableReasoningIds, FakeOpenRouterStream):
    pass


class Backend:
    def __init__(self, intent):
        self.intent = intent
        self.chat_model_factory = None  # internal calls are not under test
        self.answer_model_factory = lambda: ReasoningModel(streaming=True)

    async def classify_intent(self, question, history, config):
        return self.intent

    async def resolve_document_ids(self, session_id, client_ids):
        return []

    async def retrieve(self, question, document_ids, session_id, whole_documents):
        return []

    async def suggest_followups(self, question, answer, config):
        return []

    async def session_artifacts(self, session_id):
        return {"quizzes": [], "mindmaps": []}


def _events(text):
    return [json.loads(line[6:]) for line in text.splitlines() if line.startswith("data: ")]


def _body(thread, messages):
    return {"threadId": thread, "runId": f"run_{uuid.uuid4().hex}", "state": {}, "tools": [],
            "context": [], "forwardedProps": {}, "messages": messages}


def _user(text):
    return {"id": f"u_{uuid.uuid4().hex}", "role": "user", "content": text}


def _conversation(intent):
    app = create_standalone_app(backend=Backend(intent))
    thread = str(uuid.uuid4())

    async def go():
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                r = await client.post("/agent", json=_body(thread, [_user("Đa hình là gì?")]),
                                      headers={"accept": "text/event-stream"})
                first = _events(r.text)
                history = (await client.get(f"/threads/{thread}/messages")).json()["messages"]
                # Next turn after F5: the client echoes the history it got.
                r = await client.post("/agent", json=_body(thread, [*history, _user("cảm ơn")]),
                                      headers={"accept": "text/event-stream"})
                second = _events(r.text)
                after = (await client.get(f"/threads/{thread}/messages")).json()["messages"]
                return first, history, second, after

    return asyncio.run(go())


@pytest.mark.parametrize("intent", ["other", "summarize"])  # code_mentor, llm_stream_answer
def test_reasoning_streams_separately_and_is_restored_with_the_same_id(intent):
    first, history, _, _ = _conversation(intent)
    assert first[-1]["type"] == "RUN_FINISHED", first[-1]
    streamed_ids = {e["messageId"] for e in first if e["type"] == "REASONING_START"}
    assert len(streamed_ids) == 1, [e["type"] for e in first]
    streamed = "".join(e["delta"] for e in first if e["type"] == "REASONING_MESSAGE_CONTENT")
    assert streamed == "".join(THOUGHT)
    assert "".join(e["delta"] for e in first if e["type"] == "TEXT_MESSAGE_CONTENT") == "".join(ANSWER)

    (snapshot,) = [e for e in first if e["type"] == "MESSAGES_SNAPSHOT"]
    snapshot_reasoning = [m for m in snapshot["messages"] if m["role"] == "reasoning"]
    assert [m["id"] for m in snapshot_reasoning] == list(streamed_ids)  # client reconciles, no copy

    reasoning = [m for m in history if m["role"] == "reasoning"]
    assert reasoning == [{"id": streamed_ids.pop(), "role": "reasoning", "content": "".join(THOUGHT)}]
    roles = [m["role"] for m in history]
    assert roles.index("reasoning") == roles.index("assistant") - 1  # shown above its answer
    answer = next(m for m in history if m["role"] == "assistant")
    assert answer["content"] == "".join(ANSWER)


def test_echoed_history_does_not_duplicate_the_reasoning():
    _, history, second, after = _conversation("other")
    assert second[-1]["type"] == "RUN_FINISHED", second[-1]
    first_turn = [m for m in after if m["role"] == "reasoning"][0]
    assert first_turn == [m for m in history if m["role"] == "reasoning"][0]
    assert len([m for m in after if m["role"] == "reasoning"]) == 2  # one per answer
    assert len({m["id"] for m in after}) == len(after)


# --- production wiring ------------------------------------------------------


def test_default_backend_answers_with_the_reasoning_model(monkeypatch):
    from langchain_openrouter import ChatOpenRouter

    from app.agents.mentor_agui.backends import default_backend
    from app.core.config import settings

    monkeypatch.setattr(settings, "CHAT_ANSWER_MODEL", "openai/gpt-5-mini")
    monkeypatch.setattr(settings, "CHAT_REASONING_EFFORT", "low")
    backend = default_backend()
    model = backend.answer_model_factory()
    assert isinstance(model, StableReasoningIds) and isinstance(model, ChatOpenRouter)
    assert model.model_name == "openai/gpt-5-mini"
    assert model.reasoning == {"effort": "low", "summary": "auto"}
    assert model.temperature is None  # reasoning models reject a temperature
    assert backend.chat_model_factory().model_name == settings.CHAT_MODEL  # drafts unchanged


def test_empty_answer_model_keeps_the_chat_model_for_answers(monkeypatch):
    from app.agents.mentor_agui.backends import default_backend
    from app.core.config import settings

    monkeypatch.setattr(settings, "CHAT_ANSWER_MODEL", "")
    assert default_backend().answer_model_factory is None
