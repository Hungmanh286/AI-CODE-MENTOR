"""Mentor AG-UI graph.

Topology::

    START -> router -> qa_rag ----------------------------> END
                    -> summarize -------------------------> END
                    -> mindmap ---------------------------> END
                    -> quiz_intro -> quiz --(steer away)--> router
                                          \\-------------> END
                    -> code_mentor --(tool calls)--> ui_tools -> END
                                   \\--------------------------> END

Router order (contract 4.4): ``requested_tools`` from the composer chips
first, then intent classification (ask / summarize / mindmap / mcq / other).

The LLM/RAG touch points are the ``llm_*`` / ``retrieve_*`` hook functions
below. ``configure(backend)`` (done by ``main.py`` at startup, see
``backends.py``) plugs the real model, retrieval and storage in; without it
the hooks return deterministic placeholders (``placeholders.py``) so
``scripts/agui_selfcheck.py`` runs offline.

Streaming rules that matter for the AG-UI wire (ag-ui-langgraph 0.0.47):
* Text reaches the client only if a chat model streams it inside a node
  (on_chat_model_stream -> TEXT_MESSAGE_*). Internal LLM calls must run with
  ``INTERNAL_LLM_CONFIG`` or the client receives their tokens / tool calls.
* UI tool calls: see tools.py (pattern A = LLM bind_tools + ToolNode,
  pattern B = ``stream_ui_tool_calls``, attached to the turn's text message).
* Mid-node shared-state updates: ``publish_shared_state`` (STATE_SNAPSHOT).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any, Literal

import structlog
from langchain_core.callbacks.manager import adispatch_custom_event
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Checkpointer, Command, interrupt
from pydantic import BaseModel, Field, ValidationError

from app.agents.mentor_agui.prompts import Prompts

from . import placeholders
from .backends import INTERNAL_LLM_CONFIG, merge_config
from .reasoning import keep_reasoning
from .schemas import Intent
from .state import (
    MentorInput,
    MentorState,
    latest_user_text,
    make_job,
    message_text,
    read_artifacts,
    read_jobs,
    shared_state,
)
from .tools import (
    make_ui_tool_node,
    new_id,
    present_ui,
    stream_text,
    stream_ui_tool_calls,
    suggest_followups,
)
from .ui_catalog import CiteSources, ShowMindmap, ShowQuiz, SourceRef, SuggestFollowups

logger = structlog.get_logger(__name__)

RouteNode = Literal["qa_rag", "summarize", "mindmap", "quiz_intro", "code_mentor"]

# Composer chip id (contract 4.4) -> node.
REQUESTED_TOOL_ROUTES: dict[str, RouteNode] = {
    "generate-questions": "quiz_intro",
    "mindmap": "mindmap",
}
# Several chips in one message run one after the other in this order: the
# quiz pauses for its config form (interrupt), so it goes last and nothing
# else waits on the form.
CHIP_ORDER: list[RouteNode] = ["mindmap", "quiz_intro"]

# Resume sentinels produced by ag-ui-langgraph when RunAgentInput.resume is
# used (ag_ui_langgraph/interrupts.py, verified on 0.0.47).
AGUI_CANCELLED = "__agui_cancelled__"
AGUI_RESUME_MAP = "__agui_resume_map__"

# The model only sees text turns (no tool calls / tool results: they are UI
# payloads, can be large, and unfinished calls are rejected by providers).
LLM_HISTORY_MESSAGES = 12
# UI tools the free-form mentor may call itself; quiz/mindmap/citations are
# produced by their own nodes (interrupt, persistence, retrieval).
CODE_MENTOR_TOOLS = [present_ui, suggest_followups]

_merge_config = merge_config  # kept under this name for scripts/agui_selfcheck.py

# ---------------------------------------------------------------------------
# Hooks configuration
# ---------------------------------------------------------------------------

ChatModelFactory = Callable[[], BaseChatModel]
_chat_model_factory: ChatModelFactory | None = None  # answers (may reason)
_fast_model_factory: ChatModelFactory | None = None  # one-sentence intros
_backend: Any = None


def set_chat_model_factory(
    factory: ChatModelFactory | None, fast_factory: ChatModelFactory | None = None
) -> None:
    """Plug streaming chat models in; ``None`` = placeholders. ``fast_factory``
    (intros) defaults to ``factory``."""
    global _chat_model_factory, _fast_model_factory
    _chat_model_factory = factory
    _fast_model_factory = fast_factory or factory


def configure(backend: Any) -> None:
    """Install the real LLM/RAG/storage backend (``backends.MentorBackend``), or reset with None.

    Answers use ``backend.answer_model_factory`` (a reasoning model, see
    reasoning.py) when there is one; intros keep the fast ``chat_model_factory``.
    """
    global _backend
    _backend = backend
    fast = getattr(backend, "chat_model_factory", None) if backend else None
    answer = (getattr(backend, "answer_model_factory", None) if backend else None) or fast
    set_chat_model_factory(answer, fast)


def get_chat_model(*, fast: bool = False) -> BaseChatModel | None:
    factory = _fast_model_factory if fast else _chat_model_factory
    return factory() if factory else None


def _thread_id(config: RunnableConfig) -> str:
    return str(((config or {}).get("configurable") or {}).get("thread_id") or "")


def llm_history(messages: Sequence[BaseMessage]) -> list[BaseMessage]:
    """Last text turns of the conversation, as plain Human/AI messages."""
    turns: list[BaseMessage] = []
    for m in messages:
        text = message_text(m).strip()
        if not text:
            continue
        if isinstance(m, HumanMessage):
            turns.append(HumanMessage(content=text))
        elif isinstance(m, AIMessage):
            turns.append(AIMessage(content=text))
    return turns[-LLM_HISTORY_MESSAGES:]


# ---------------------------------------------------------------------------
# LLM / retrieval hooks
# ---------------------------------------------------------------------------


async def llm_classify_intent(
    question: str, history: Sequence[BaseMessage], config: RunnableConfig
) -> Intent:
    """Latest user message -> ``ask | summarize | mindmap | mcq | other``."""
    if _backend is not None:
        return await _backend.classify_intent(question, history, config)
    return placeholders.classify(question)


NO_QUIZ_REQUEST: dict[str, Any] = {"topic": None, "count": None, "difficulty": None}


async def llm_extract_quiz_request(question: str, config: RunnableConfig) -> dict[str, Any]:
    """Topic / count / difficulty stated in the message; all None when unknown.

    Optional: a failure only loses the pre-filled form values, never the quiz.
    """
    if _backend is None:
        return dict(NO_QUIZ_REQUEST)
    try:
        return await _backend.extract_quiz_request(question, config)
    except Exception as exc:
        logger.warning(f"quiz request not extracted: {exc!r}")
        return dict(NO_QUIZ_REQUEST)


async def resolve_document_ids(client_ids: Sequence[str], config: RunnableConfig) -> list[str]:
    """Documents of this session the run may use (see agui_documents.select_documents)."""
    if _backend is not None:
        return await _backend.resolve_document_ids(_thread_id(config), list(client_ids))
    return list(client_ids)


async def retrieve_chunks(
    question: str, document_ids: Sequence[str], config: RunnableConfig, *, whole_documents: bool = False
) -> list[dict]:
    """Passages (``whole_documents=False``) or full texts of the documents:
    ``[{file_id, file_name, page, text}]``."""
    if _backend is not None:
        return await _backend.retrieve(question, list(document_ids), _thread_id(config), whole_documents)
    return placeholders.chunks(document_ids)


async def llm_stream_answer(
    system_prompt: str,
    messages: Sequence[BaseMessage],
    config: RunnableConfig,
    *,
    placeholder: str,
    fast: bool = False,
) -> AIMessage:
    """Stream an assistant answer to the client (TEXT_MESSAGE_*, and REASONING_*
    when the model reasons); returns the message to store, reasoning included.

    Passing the node ``config`` is what lets ag-ui-langgraph stream the tokens.
    ``fast``: the non-reasoning model, for one-sentence intros.
    """
    model = get_chat_model(fast=fast)
    if model is None:
        return await stream_text(placeholder, config)
    result = await model.ainvoke([SystemMessage(content=system_prompt), *llm_history(messages)], config)
    return keep_reasoning(AIMessage(
        id=result.id, content=result.content, additional_kwargs=result.additional_kwargs))


async def llm_suggest_followups(question: str, answer: str, config: RunnableConfig) -> list[str]:
    if _backend is not None:
        return await _backend.suggest_followups(question, answer, config)
    return list(placeholders.FOLLOWUPS)


async def llm_generate_quiz(
    topic: str, chunks: Sequence[dict], count: int, difficulty: str, config: RunnableConfig
) -> ShowQuiz:
    if _backend is not None:
        return await _backend.generate_quiz(topic, chunks, count, difficulty, config)
    return placeholders.quiz(count, difficulty)


async def llm_generate_mindmap(topic: str, chunks: Sequence[dict], config: RunnableConfig) -> ShowMindmap:
    if _backend is not None:
        return await _backend.generate_mindmap(topic, chunks, config)
    return placeholders.mindmap()


async def store_quiz(quiz: ShowQuiz, chunks: Sequence[dict], config: RunnableConfig) -> tuple[str, ShowQuiz]:
    """Persist the quiz; returns (artifact id, quiz carrying the stored question ids)."""
    if _backend is not None:
        return await _backend.save_quiz(_thread_id(config), quiz, chunks)
    return new_id("quiz"), quiz


async def store_mindmap(result: ShowMindmap, config: RunnableConfig) -> str:
    if _backend is not None:
        return await _backend.save_mindmap(_thread_id(config), result)
    return new_id("mindmap")


async def load_artifacts(state: Mapping[str, Any], config: RunnableConfig) -> dict[str, Any]:
    """Artifacts of the session: stored ones (source of truth) or, offline, the state's."""
    if _backend is not None:
        return await _backend.session_artifacts(_thread_id(config))
    return dict(read_artifacts(state))


# ---------------------------------------------------------------------------
# Shared-state helper
# ---------------------------------------------------------------------------


async def publish_shared_state(
    artifacts: Mapping[str, Any], jobs: Mapping[str, Any], config: RunnableConfig
) -> None:
    """Push artifacts/jobs to the client mid-node (STATE_SNAPSHOT).

    Uses ag-ui-langgraph's ``manually_emit_state`` custom event. The node must
    still *return* the same values so the checkpointer stores them.
    """
    await adispatch_custom_event(
        "manually_emit_state",
        shared_state({"artifacts": dict(artifacts), "jobs": dict(jobs)}),
        config=config,
    )


def _citations(chunks: Sequence[dict]) -> CiteSources:
    return CiteSources(
        sources=[
            SourceRef(file_id=c["file_id"], file_name=c["file_name"], page=c.get("page"), quote=c["text"][:300])
            for c in chunks
        ]
    )


def _context(chunks: Sequence[dict]) -> str:
    return "\n\n---\n\n".join(f"[{c['file_name']}]\n{c['text']}" for c in chunks)


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


def _next_route(state: Mapping[str, Any]) -> tuple[str, list[str]]:
    """Next chip node of this run (or END) and the ones left after it."""
    pending = list(state.get("pending_routes") or [])
    return (pending[0], pending[1:]) if pending else (END, [])


async def router(
    state: MentorState, config: RunnableConfig
) -> Command[Literal["qa_rag", "summarize", "mindmap", "quiz_intro", "code_mentor", "__end__"]]:
    """Start of every new user turn (a resume never reaches it: LangGraph
    resumes the interrupted node).

    * Shared state: artifacts are re-read from storage (source of truth) and
      jobs of earlier runs are dropped, so finished jobs never pile up.
    * Composer chips come first and beat intent classification; several chips
      run one after the other (``CHIP_ORDER``).
    """
    doc_ids = await resolve_document_ids(state.get("active_document_ids") or [], config)
    update: dict[str, Any] = {
        "active_document_ids": doc_ids,
        "artifacts": await load_artifacts(state, config),
        "jobs": {},
        "pending_routes": [],
    }
    chips = {REQUESTED_TOOL_ROUTES[t] for t in state.get("requested_tools") or [] if t in REQUESTED_TOOL_ROUTES}
    routes = [r for r in CHIP_ORDER if r in chips]
    if routes:
        if await _documents_unreadable(routes, doc_ids, config):
            return await _report_unreadable_documents(update, config)
        return Command(goto=routes[0], update={**update, "route": routes[0], "pending_routes": routes[1:]})

    question = latest_user_text(state) or ""
    intent = await llm_classify_intent(question, state.get("messages") or [], config)
    target: RouteNode
    if intent == "summarize":
        target = "summarize"
    elif intent == "mindmap":
        target = "mindmap"
    elif intent == "mcq":
        target = "quiz_intro"
    elif intent == "ask" and doc_ids:
        target = "qa_rag"
    else:  # "ask" without documents, "other"
        target = "code_mentor"
    if await _documents_unreadable([target], doc_ids, config):
        return await _report_unreadable_documents(update, config)
    return Command(goto=target, update={**update, "route": target})


# Nodes that work on the whole text of the documents switched on.
WHOLE_DOCUMENT_ROUTES = frozenset({"summarize", "mindmap", "quiz_intro"})


async def _documents_unreadable(routes: Sequence[str], doc_ids: Sequence[str], config: RunnableConfig) -> bool:
    """Documents are switched on but none has any text (e.g. the PDF parse failed).

    Without this, summarize/mindmap/quiz fell back to "no document" and made
    content up from the chat message (a mind map about "tạo cho mình").
    Without any document switched on, general knowledge stays allowed.
    """
    if not doc_ids or not WHOLE_DOCUMENT_ROUTES.intersection(routes):
        return False
    return not await retrieve_chunks("", doc_ids, config, whole_documents=True)


async def _report_unreadable_documents(update: dict[str, Any], config: RunnableConfig) -> Command:
    notice = await stream_text(Prompts.DOCUMENTS_UNREADABLE, config)
    return Command(goto=END, update={**update, "messages": [notice]})


async def qa_rag(state: MentorState, config: RunnableConfig) -> dict[str, Any]:
    question = latest_user_text(state) or ""
    chunks = await retrieve_chunks(question, state.get("active_document_ids") or [], config)
    system = Prompts.QA_RAG.format(context=_context(chunks)) if chunks else Prompts.QA_NO_PASSAGE
    answer = await llm_stream_answer(system, state["messages"], config, placeholder=placeholders.QA_ANSWER)
    calls: list[Any] = []
    if chunks:
        calls.append(("cite_sources", _citations(chunks)))
    followups = await llm_suggest_followups(question, message_text(answer), config)
    if followups:
        calls.append(("suggest_followups", SuggestFollowups(questions=followups[:3])))
    return {"messages": await stream_ui_tool_calls(calls, config, attach_to=answer)}


async def summarize(state: MentorState, config: RunnableConfig) -> dict[str, Any]:
    question = latest_user_text(state) or ""
    chunks = await retrieve_chunks(
        question, state.get("active_document_ids") or [], config, whole_documents=True
    )
    system = Prompts.SUMMARIZE.format(context=_context(chunks)) if chunks else Prompts.SUMMARIZE_NO_DOCUMENT
    answer = await llm_stream_answer(system, state["messages"], config, placeholder=placeholders.SUMMARY)
    calls: list[Any] = [("cite_sources", _citations(chunks))] if chunks else []
    return {"messages": await stream_ui_tool_calls(calls, config, attach_to=answer)}


async def mindmap(state: MentorState, config: RunnableConfig) -> Command[Literal["quiz_intro", "__end__"]]:
    artifacts = read_artifacts(state)
    jobs = read_jobs(state)
    job_id = new_id("job")
    jobs[job_id] = make_job("mindmap", "Đang vẽ sơ đồ tư duy", 0, "running")
    await publish_shared_state(artifacts, jobs, config)
    goto, rest = _next_route(state)

    question = latest_user_text(state) or ""
    try:
        chunks = await retrieve_chunks(
            question, state.get("active_document_ids") or [], config, whole_documents=True
        )
        result = await llm_generate_mindmap(question, chunks, config)
    except Exception as exc:  # any failure must end the job, never leave it "running"
        logger.warning(f"mindmap generation failed: {exc!r}")
        jobs[job_id] = make_job("mindmap", "Vẽ sơ đồ tư duy thất bại", 100, "error")
        await publish_shared_state(artifacts, jobs, config)
        failed = await stream_text("Xin lỗi, mình chưa vẽ được sơ đồ tư duy. Bạn thử lại nhé.", config)
        return Command(goto=goto, update={
            "messages": [failed], "artifacts": artifacts, "jobs": jobs, "pending_routes": rest})

    intro = await llm_stream_answer(
        Prompts.MINDMAP_INTRO.format(title=result.title), [HumanMessage(content=Prompts.INTRO_REQUEST)],
        config, placeholder=placeholders.MINDMAP_INTRO, fast=True,
    )
    messages = await stream_ui_tool_calls([("show_mindmap", result)], config, attach_to=intro)
    try:
        artifacts["mindmaps"].append({"id": await store_mindmap(result, config), "title": result.title})
        jobs[job_id] = make_job("mindmap", "Đã vẽ sơ đồ tư duy", 100, "done")
    except Exception as exc:
        logger.warning(f"mindmap not stored: {exc!r}")
        jobs[job_id] = make_job("mindmap", "Không lưu được sơ đồ tư duy", 100, "error")
    await publish_shared_state(artifacts, jobs, config)
    return Command(goto=goto, update={
        "messages": messages, "artifacts": artifacts, "jobs": jobs, "pending_routes": rest})


class QuizConfigPayload(BaseModel):
    """Resume payload of the ``quiz_config`` interrupt (contract 4.6)."""

    count: int = Field(default=10, ge=1, le=30)
    difficulty: Literal["easy", "medium", "hard"] = "medium"


QUIZ_DEFAULTS = {"count": 10, "difficulty": "medium"}


async def quiz_intro(state: MentorState, config: RunnableConfig) -> dict[str, Any]:
    """Assistant text BEFORE the interrupt (contract 4.6).

    Its own node on purpose: a node that calls ``interrupt()`` is re-executed
    from the top on resume, so text streamed there would be streamed twice.
    """
    request = await llm_extract_quiz_request(latest_user_text(state) or "", config)
    intro = await llm_stream_answer(
        Prompts.QUIZ_INTRO, [HumanMessage(content=Prompts.INTRO_REQUEST)], config,
        placeholder=placeholders.QUIZ_INTRO, fast=True,
    )
    return {"messages": [intro], "quiz_request": request}


def _parse_quiz_resume(answer: Any) -> QuizConfigPayload | None:
    """``None`` means cancelled. Handles the three shapes ag-ui-langgraph sends."""
    if isinstance(answer, Mapping) and AGUI_RESUME_MAP in answer:
        entries = list((answer.get(AGUI_RESUME_MAP) or {}).values())
        entry = entries[0] if entries else {"status": "cancelled"}
        if entry.get("status") != "resolved":
            return None
        answer = entry.get("payload")
    if isinstance(answer, Mapping) and answer.get(AGUI_CANCELLED):
        return None
    try:
        return QuizConfigPayload.model_validate(answer or {})
    except ValidationError as exc:
        logger.warning(f"invalid quiz_config payload {answer!r}: {exc}; using defaults")
        return QuizConfigPayload()


async def quiz(
    state: MentorState, config: RunnableConfig
) -> Command[Literal["router", "mindmap", "__end__"]]:
    """Ask for quiz_config, then generate. Resume outcomes (contract 4.6):

    * resolved                     -> generate (even if a new user message came too)
    * cancelled, no new message    -> "Đã hủy sinh câu hỏi."
    * cancelled + new user message -> steer away: route the new message again

    A "new user message" reaches the state through ``Command(update=...)`` in
    ``agent.MentorLangGraphAgent.prepare_stream``.
    """
    # A resumed node re-runs from the top: nothing with side effects before interrupt().
    request = state.get("quiz_request") or NO_QUIZ_REQUEST
    topic = request.get("topic")
    answer = interrupt(
        {
            "reason": "input_required",
            "message": (
                f"Sinh câu hỏi về: {topic}"
                if topic and not state.get("active_document_ids")
                else "Sinh câu hỏi từ tài liệu đang bật?"
            ),
            "metadata": {
                "kind": "quiz_config",
                # What the learner stated pre-fills the form ("tạo 3 câu" -> 3).
                "defaults": {
                    "count": request.get("count") or QUIZ_DEFAULTS["count"],
                    "difficulty": request.get("difficulty") or QUIZ_DEFAULTS["difficulty"],
                },
                "documents": [],  # item shape not defined by contract 4.6
            },
        }
    )
    cfg = _parse_quiz_resume(answer)

    if cfg is None:
        messages = state.get("messages") or []
        if messages and isinstance(messages[-1], HumanMessage):
            return Command(goto="router")  # steer away
        cancelled = await stream_text(Prompts.QUIZ_CANCELLED, config)
        return Command(goto=END, update={"messages": [cancelled]})

    artifacts = read_artifacts(state)
    jobs = read_jobs(state)
    job_id = new_id("job")
    jobs[job_id] = make_job("quiz", "Đang sinh câu hỏi", 0, "running")
    await publish_shared_state(artifacts, jobs, config)

    goto, rest = _next_route(state)
    question = latest_user_text(state) or ""
    try:
        chunks = await retrieve_chunks(
            question, state.get("active_document_ids") or [], config, whole_documents=True
        )
        jobs[job_id] = make_job("quiz", "Đang sinh câu hỏi", 40, "running")
        await publish_shared_state(artifacts, jobs, config)
        # The extracted topic, not the whole sentence: "tạo 3 câu hỏi toán lớp 1" with
        # 5 chosen in the form would otherwise ask for 3 and 5 questions at once.
        result = await llm_generate_quiz(topic or question, chunks, cfg.count, cfg.difficulty, config)
        jobs[job_id] = make_job("quiz", "Đang sinh câu hỏi", 80, "running")
        await publish_shared_state(artifacts, jobs, config)
    except Exception as exc:  # any failure must end the job, never leave it "running"
        logger.warning(f"quiz generation failed: {exc!r}")
        jobs[job_id] = make_job("quiz", "Sinh câu hỏi thất bại", 100, "error")
        await publish_shared_state(artifacts, jobs, config)
        failed = await stream_text("Xin lỗi, mình chưa sinh được câu hỏi. Bạn thử lại nhé.", config)
        return Command(goto=goto, update={
            "messages": [failed], "artifacts": artifacts, "jobs": jobs, "pending_routes": rest})

    try:
        quiz_id, result = await store_quiz(result, chunks, config)
        artifacts["quizzes"].append({"id": quiz_id, "title": result.title, "count": len(result.questions)})
        jobs[job_id] = make_job("quiz", "Đã sinh câu hỏi", 100, "done")
    except Exception as exc:  # still show the quiz; it just is not saved
        logger.warning(f"quiz not stored: {exc!r}")
        jobs[job_id] = make_job("quiz", "Không lưu được bộ câu hỏi", 100, "error")

    # Attach to the quiz_intro message: the client resumes that interrupted
    # message, and live/snapshot/history then agree on one assistant message.
    intro = next(
        (m for m in reversed(state.get("messages") or []) if isinstance(m, AIMessage) and not m.tool_calls),
        None,
    )
    messages = await stream_ui_tool_calls([("show_quiz", result)], config, attach_to=intro)
    await publish_shared_state(artifacts, jobs, config)
    return Command(goto=goto, update={
        "messages": messages, "artifacts": artifacts, "jobs": jobs, "pending_routes": rest})


async def code_mentor(state: MentorState, config: RunnableConfig) -> Command[Literal["ui_tools", "__end__"]]:
    """General programming mentor.

    Real path (pattern A): the model may call ``present_ui`` /
    ``suggest_followups``; tool-call chunks stream to the client with
    parentMessageId, then ``ui_tools`` (ToolNode) returns "ok".
    """
    model = get_chat_model()
    if model is not None:
        response = await model.bind_tools(CODE_MENTOR_TOOLS).ainvoke(
            [SystemMessage(content=Prompts.CODE_MENTOR), *llm_history(state["messages"])], config
        )
        if getattr(response, "tool_calls", None):
            return Command(goto="ui_tools", update={"messages": [keep_reasoning(response)]})
        # Text-only answer: add follow-ups ourselves (pattern B, same message)
        # so every plain answer offers next questions, as the WS chat did.
        answer = keep_reasoning(AIMessage(
            id=response.id, content=response.content, additional_kwargs=response.additional_kwargs))
        calls: list[Any] = []
        followups = await llm_suggest_followups(latest_user_text(state) or "", answer.content, config)
        if followups:
            calls.append(("suggest_followups", SuggestFollowups(questions=followups[:3])))
        return Command(goto=END, update={"messages": await stream_ui_tool_calls(calls, config, attach_to=answer)})

    # Placeholder path (pattern B).
    question = (latest_user_text(state) or "").lower()
    calls: list[Any] = []
    if any(k in question for k in ("so sánh", "khác", "compare")):
        text = await stream_text("So sánh nhanh **abstract class** và **interface**:", config)
        calls.append(("present_ui", placeholders.present_ui()))
    else:
        text = await stream_text(
            "Mình là trợ lý lập trình. Hãy hỏi về OOP, Java hoặc đoạn code bạn đang viết.", config
        )
    calls.append(("suggest_followups", SuggestFollowups(questions=list(placeholders.MENTOR_FOLLOWUPS))))
    return Command(goto=END, update={"messages": await stream_ui_tool_calls(calls, config, attach_to=text)})


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------


def build_graph(checkpointer: Checkpointer = None):
    """Compile the graph. ``checkpointer`` is required for interrupts/history."""
    builder = StateGraph(MentorState, input_schema=MentorInput)
    builder.add_node("router", router)
    builder.add_node("qa_rag", qa_rag)
    builder.add_node("summarize", summarize)
    builder.add_node("mindmap", mindmap)
    builder.add_node("quiz_intro", quiz_intro)
    builder.add_node("quiz", quiz)
    builder.add_node("code_mentor", code_mentor)
    builder.add_node("ui_tools", make_ui_tool_node())

    builder.add_edge(START, "router")
    builder.add_edge("qa_rag", END)
    builder.add_edge("summarize", END)
    builder.add_edge("quiz_intro", "quiz")
    builder.add_edge("ui_tools", END)
    return builder.compile(checkpointer=checkpointer)


__all__ = ["INTERNAL_LLM_CONFIG", "build_graph", "configure", "set_chat_model_factory"]
