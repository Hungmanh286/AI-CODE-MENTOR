"""The AG-UI graph uses the configured backend (BACKEND-PLAN GĐ2, GĐ3)."""

import asyncio
import uuid

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver

from app.agents.mentor_agui import graph as graph_module
from app.agents.mentor_agui.ui_catalog import (
    MindmapNode,
    QuizQuestion,
    ShowMindmap,
    ShowQuiz,
)


class FakeModel(BaseChatModel):
    bound: list = []

    @property
    def _llm_type(self) -> str:
        return "fake"

    def bind_tools(self, tools, **kwargs):
        FakeModel.bound = [t.name for t in tools]
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="Trả lời.", id=f"m_{uuid.uuid4().hex}"))])


CHUNK = {"file_id": "f1", "file_name": "oop.pdf", "page": None, "text": "Đa hình là ..."}


class FakeBackend:
    def __init__(self, intent="ask", doc_ids=("f1",)):
        self.intent = intent
        self.doc_ids = list(doc_ids)
        self.calls = []
        self.chat_model_factory = FakeModel

    async def classify_intent(self, question, history, config):
        return self.intent

    async def resolve_document_ids(self, session_id, client_ids):
        self.calls.append(("resolve", session_id, list(client_ids)))
        return self.doc_ids

    async def retrieve(self, question, document_ids, session_id, whole_documents):
        self.calls.append(("retrieve", list(document_ids), session_id, whole_documents))
        return [CHUNK] if document_ids else []

    async def suggest_followups(self, question, answer, config):
        return ["Câu tiếp?"]

    async def generate_quiz(self, topic, chunks, count, difficulty, config):
        return ShowQuiz(title="Quiz", questions=[
            QuizQuestion(id=f"q{i + 1}", question=f"C{i}?", options=["a", "b"], answer_index=0,
                         explanation="e", difficulty=difficulty)
            for i in range(count)
        ])

    async def generate_mindmap(self, topic, chunks, config):
        return ShowMindmap(title="Sơ đồ", root=MindmapNode(id="n", label="Gốc"))


@pytest.fixture
def backend():
    fake = FakeBackend()
    graph_module.configure(fake)
    yield fake
    graph_module.configure(None)


def _run(text, context_state=None):
    graph = graph_module.build_graph(checkpointer=InMemorySaver())
    thread = str(uuid.uuid4())
    state = {"messages": [HumanMessage(content=text, id=f"u_{uuid.uuid4().hex}")], **(context_state or {})}
    out = asyncio.run(graph.ainvoke(state, {"configurable": {"thread_id": thread}}))
    return thread, out


def _tool_calls(out, name):
    return [c for m in out["messages"] if isinstance(m, AIMessage) for c in m.tool_calls if c["name"] == name]


def test_router_resolves_session_documents_and_answers_with_citations(backend):
    thread, out = _run("Đa hình là gì?", {"active_document_ids": []})
    assert ("resolve", thread, []) in backend.calls
    assert ("retrieve", ["f1"], thread, False) in backend.calls
    cites = _tool_calls(out, "cite_sources")
    assert cites and cites[0]["args"]["sources"][0]["file_id"] == "f1"
    assert _tool_calls(out, "suggest_followups")[0]["args"] == {"questions": ["Câu tiếp?"]}


def test_question_without_documents_goes_to_code_mentor_with_two_ui_tools(backend):
    backend.doc_ids = []
    _, out = _run("Đa hình là gì?")
    assert sorted(FakeModel.bound) == ["present_ui", "suggest_followups"]
    assert out["route"] == "code_mentor"


def test_summarize_reads_whole_documents(backend):
    backend.intent = "summarize"
    thread, _ = _run("tóm tắt tài liệu")
    assert ("retrieve", ["f1"], thread, True) in backend.calls


def test_plain_mentor_answer_gets_followups_attached_to_the_same_message(backend):
    backend.doc_ids = []
    _, out = _run("Đa hình là gì?")
    answers = [m for m in out["messages"] if isinstance(m, AIMessage)]
    assert len(answers) == 1, answers
    assert answers[0].content == "Trả lời."
    assert [c["name"] for c in answers[0].tool_calls] == ["suggest_followups"]
