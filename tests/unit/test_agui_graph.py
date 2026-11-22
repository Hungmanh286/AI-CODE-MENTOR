"""The AG-UI graph uses the configured backend (BACKEND-PLAN GĐ2, GĐ3)."""

import asyncio
import uuid

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.agents.mentor_agui import graph as graph_module
from app.agents.mentor_agui.ui_catalog import (
    MindmapNode,
    QuizQuestion,
    ShowMindmap,
    ShowQuiz,
)


class FakeModel(BaseChatModel):
    bound: list = []
    seen: list = []  # messages of every call, newest last

    @property
    def _llm_type(self) -> str:
        return "fake"

    def bind_tools(self, tools, **kwargs):
        FakeModel.bound = [t.name for t in tools]
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        FakeModel.seen.append(list(messages))
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="Trả lời.", id=f"m_{uuid.uuid4().hex}"))])


CHUNK = {"file_id": "f1", "file_name": "oop.pdf", "page": None, "text": "Đa hình là ..."}


class FakeBackend:
    def __init__(self, intent="ask", doc_ids=("f1",)):
        self.intent = intent
        self.doc_ids = list(doc_ids)
        self.calls = []
        self.chat_model_factory = FakeModel
        self.stored = {"quizzes": [], "mindmaps": []}
        self.fail_save = False
        self.mindmap_error = None
        self.unreadable = False  # documents selected but no text (e.g. PDF parse failed)
        self.quiz_request = {"topic": None, "count": None, "difficulty": None}

    async def classify_intent(self, question, history, config):
        return self.intent

    async def resolve_document_ids(self, session_id, client_ids):
        self.calls.append(("resolve", session_id, list(client_ids)))
        return self.doc_ids

    async def retrieve(self, question, document_ids, session_id, whole_documents):
        self.calls.append(("retrieve", list(document_ids), session_id, whole_documents))
        return [CHUNK] if document_ids and not self.unreadable else []

    async def suggest_followups(self, question, answer, config):
        return ["Câu tiếp?"]

    async def extract_quiz_request(self, question, config):
        self.calls.append(("extract_quiz_request", question))
        if isinstance(self.quiz_request, Exception):
            raise self.quiz_request
        return dict(self.quiz_request)

    async def generate_quiz(self, topic, chunks, count, difficulty, config):
        self.calls.append(("generate_quiz", topic, count, difficulty))
        return ShowQuiz(title="Quiz", questions=[
            QuizQuestion(id=f"q{i + 1}", question=f"C{i}?", options=["a", "b"], answer_index=0,
                         explanation="e", difficulty=difficulty)
            for i in range(count)
        ])

    async def generate_mindmap(self, topic, chunks, config):
        if self.mindmap_error:
            raise self.mindmap_error
        return ShowMindmap(title="Sơ đồ", root=MindmapNode(id="n", label="Gốc"))

    async def save_quiz(self, session_id, quiz, chunks):
        if self.fail_save:
            raise RuntimeError("db down")
        saved = quiz.model_copy(update={"questions": [
            q.model_copy(update={"id": f"db_{q.id}"}) for q in quiz.questions]})
        self.stored["quizzes"].append({"id": "proj1", "title": quiz.title, "count": len(quiz.questions)})
        return "proj1", saved

    async def save_mindmap(self, session_id, mindmap):
        self.stored["mindmaps"].append({"id": "mm1", "title": mindmap.title})
        return "mm1"

    async def session_artifacts(self, session_id):
        return {k: list(v) for k, v in self.stored.items()}


@pytest.fixture
def backend():
    fake = FakeBackend()
    FakeModel.seen = []
    graph_module.configure(fake)
    yield fake
    graph_module.configure(None)


def _run(text, context_state=None, graph=None, thread=None):
    graph = graph or graph_module.build_graph(checkpointer=InMemorySaver())
    thread = thread or str(uuid.uuid4())
    state = {"messages": [HumanMessage(content=text, id=f"u_{uuid.uuid4().hex}")], **(context_state or {})}
    out = asyncio.run(graph.ainvoke(state, {"configurable": {"thread_id": thread}}))
    return thread, out


def _resume(graph, thread, payload):
    return asyncio.run(graph.ainvoke(Command(resume=payload), {"configurable": {"thread_id": thread}}))


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


# --- GĐ3: storage, jobs, errors, several chips -----------------------------


def test_resolved_quiz_is_stored_and_shown_with_db_ids(backend):
    backend.intent = "mcq"
    graph = graph_module.build_graph(checkpointer=InMemorySaver())
    thread, out = _run("tạo quiz", graph=graph)
    assert "__interrupt__" in out
    out = _resume(graph, thread, {"count": 2, "difficulty": "easy"})
    quiz = _tool_calls(out, "show_quiz")[0]["args"]
    assert [q["id"] for q in quiz["questions"]] == ["db_q1", "db_q2"]
    assert out["artifacts"]["quizzes"] == [{"id": "proj1", "title": "Quiz", "count": 2}]
    assert [j["status"] for j in out["jobs"].values()] == ["done"]


def test_quiz_that_cannot_be_saved_is_still_shown_but_job_is_error(backend):
    backend.intent = "mcq"
    backend.fail_save = True
    graph = graph_module.build_graph(checkpointer=InMemorySaver())
    thread, _ = _run("tạo quiz", graph=graph)
    out = _resume(graph, thread, {"count": 2, "difficulty": "easy"})
    assert len(_tool_calls(out, "show_quiz")[0]["args"]["questions"]) == 2
    assert out["artifacts"]["quizzes"] == []
    assert [j["status"] for j in out["jobs"].values()] == ["error"]


def test_unexpected_error_in_mindmap_marks_job_error_and_apologises(backend):
    backend.intent = "mindmap"
    backend.mindmap_error = RuntimeError("provider timeout")
    _, out = _run("vẽ sơ đồ")
    assert [j["status"] for j in out["jobs"].values()] == ["error"]
    assert "Xin lỗi" in out["messages"][-1].content
    assert not _tool_calls(out, "show_mindmap")


def test_mindmap_is_stored_and_listed_with_its_db_id(backend):
    backend.intent = "mindmap"
    _, out = _run("vẽ sơ đồ")
    assert out["artifacts"]["mindmaps"] == [{"id": "mm1", "title": "Sơ đồ"}]


def test_new_run_projects_stored_artifacts_and_drops_finished_jobs(backend):
    backend.intent = "mindmap"
    graph = graph_module.build_graph(checkpointer=InMemorySaver())
    thread, out = _run("vẽ sơ đồ", graph=graph)
    assert len(out["jobs"]) == 1
    backend.stored["quizzes"].append({"id": "old_ws_quiz", "title": "Cũ", "count": 5})
    backend.intent = "other"
    _, out = _run("cảm ơn", graph=graph, thread=thread)
    assert out["jobs"] == {}
    assert out["artifacts"]["quizzes"] == [{"id": "old_ws_quiz", "title": "Cũ", "count": 5}]
    assert out["artifacts"]["mindmaps"] == [{"id": "mm1", "title": "Sơ đồ"}]


def test_two_chips_draw_the_mindmap_then_ask_for_the_quiz_config(backend):
    graph = graph_module.build_graph(checkpointer=InMemorySaver())
    thread, out = _run("ôn tập", {"requested_tools": ["generate-questions", "mindmap"]}, graph=graph)
    assert _tool_calls(out, "show_mindmap")
    assert "__interrupt__" in out
    out = _resume(graph, thread, {"count": 1, "difficulty": "medium"})
    assert len(_tool_calls(out, "show_quiz")[0]["args"]["questions"]) == 1


# --- documents switched on but unreadable (PDF parse failed) ---------------


def _texts(out):
    return [m.content for m in out["messages"] if isinstance(m, AIMessage) and m.content]


@pytest.mark.parametrize("intent", ["mindmap", "summarize"])
def test_unreadable_documents_are_reported_not_replaced_by_general_knowledge(backend, intent):
    from app.agents.mentor_agui.prompts import Prompts

    backend.intent = intent
    backend.unreadable = True
    _, out = _run("tạo cho mình")
    assert _texts(out)[-1] == Prompts.DOCUMENTS_UNREADABLE
    assert not _tool_calls(out, "show_mindmap")
    assert out["jobs"] == {}


def test_quiz_on_unreadable_documents_does_not_ask_for_the_config(backend):
    from app.agents.mentor_agui.prompts import Prompts

    backend.intent = "mcq"
    backend.unreadable = True
    _, out = _run("tạo quiz")
    assert "__interrupt__" not in out
    assert _texts(out)[-1] == Prompts.DOCUMENTS_UNREADABLE


def test_two_chips_on_unreadable_documents_report_it_once(backend):
    from app.agents.mentor_agui.prompts import Prompts

    backend.unreadable = True
    _, out = _run("ôn tập", {"requested_tools": ["generate-questions", "mindmap"]})
    assert "__interrupt__" not in out
    assert _texts(out).count(Prompts.DOCUMENTS_UNREADABLE) == 1


def test_mindmap_without_any_document_still_uses_general_knowledge(backend):
    backend.intent = "mindmap"
    backend.doc_ids = []
    _, out = _run("vẽ sơ đồ về đa hình")
    assert _tool_calls(out, "show_mindmap")


@pytest.mark.parametrize("intent", ["mindmap", "mcq"])
def test_intro_sentence_is_not_asked_to_answer_the_conversation(backend, intent):
    """The intro got the whole chat history and the model answered the chat
    instead (seen live: Java code / an ASCII mind map above the real one)."""
    backend.intent = intent
    _run("viết code ví dụ ngoại lệ tự tạo")
    intro_call = FakeModel.seen[-1]
    assert not any("viết code ví dụ" in str(m.content) for m in intro_call)


# --- quiz parameters stated in the message ("tạo 3 câu hỏi toán lớp 1") ----


def _interrupt(out):
    return out["__interrupt__"][0].value


def test_quiz_form_defaults_to_the_count_and_topic_the_learner_stated(backend):
    backend.intent = "mcq"
    backend.doc_ids = []
    backend.quiz_request = {"topic": "toán lớp 1", "count": 3, "difficulty": "easy"}
    _, out = _run("tạo 3 câu hỏi toán lớp 1")
    value = _interrupt(out)
    assert value["metadata"]["defaults"] == {"count": 3, "difficulty": "easy"}
    assert value["message"] == "Sinh câu hỏi về: toán lớp 1"


def test_quiz_is_generated_on_the_extracted_topic_with_the_form_count(backend):
    backend.intent = "mcq"
    backend.doc_ids = []
    backend.quiz_request = {"topic": "toán lớp 1", "count": 3, "difficulty": None}
    graph = graph_module.build_graph(checkpointer=InMemorySaver())
    thread, _ = _run("tạo 3 câu hỏi toán lớp 1", graph=graph)
    _resume(graph, thread, {"count": 5, "difficulty": "medium"})
    assert ("generate_quiz", "toán lớp 1", 5, "medium") in backend.calls


def test_quiz_form_with_documents_keeps_asking_about_the_documents(backend):
    backend.intent = "mcq"
    backend.quiz_request = {"topic": None, "count": 4, "difficulty": None}
    _, out = _run("tạo 4 câu hỏi")
    value = _interrupt(out)
    assert value["message"] == "Sinh câu hỏi từ tài liệu đang bật?"
    assert value["metadata"]["defaults"] == {"count": 4, "difficulty": "medium"}


def test_quiz_still_works_when_the_parameters_cannot_be_extracted(backend):
    backend.intent = "mcq"
    backend.quiz_request = RuntimeError("provider down")
    graph = graph_module.build_graph(checkpointer=InMemorySaver())
    thread, out = _run("tạo quiz", graph=graph)
    assert _interrupt(out)["metadata"]["defaults"] == {"count": 10, "difficulty": "medium"}
    out = _resume(graph, thread, {"count": 2, "difficulty": "easy"})
    assert ("generate_quiz", "tạo quiz", 2, "easy") in backend.calls
