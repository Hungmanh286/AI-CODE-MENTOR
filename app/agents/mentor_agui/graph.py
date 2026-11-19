"""Mentor LangGraph graph (reference skeleton).

Topology::

    START -> router -> qa_rag ----------------------------> END
                    -> summarize -------------------------> END
                    -> mindmap ---------------------------> END
                    -> quiz_intro -> quiz --(steer away)--> router
                                          \\-------------> END
                    -> code_mentor --(tool calls)--> ui_tools -> END
                                   \\--------------------------> END

Router order (PLAN 6.F): ``requested_tools`` from the composer chips first,
then intent classification (ask / summarize / mindmap / MCQ / other, as in
prompt-routing-mechanism.drawio).

LLM calls are marked ``# TODO(LLM)`` with their exact input/output. Until they
are implemented the functions return deterministic placeholder data so the
graph runs end to end (selfcheck.py, scripts/agui-smoke.mjs). Placeholders are
never meant for production.

Streaming rules that matter for the AG-UI wire (verified on ag-ui-langgraph
0.0.47, see README):
* Text reaches the client only if a chat model streams it inside a node
  (on_chat_model_stream -> TEXT_MESSAGE_*). Internal LLM calls (classification,
  structured generation) must run with ``INTERNAL_LLM_CONFIG`` or the client
  will receive their tokens / tool calls.
* UI tool calls: see tools.py (pattern A = LLM bind_tools + ToolNode,
  pattern B = ``stream_ui_tool_calls``, attached to the turn's text message).
* Mid-node shared-state updates: ``publish_shared_state`` (STATE_SNAPSHOT).
"""

from __future__ import annotations

import re
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
from typing_extensions import TypedDict

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
from .tools import UI_TOOLS, make_ui_tool_node, new_id, stream_text, stream_ui_tool_calls
from .ui_catalog import (
    CalloutBlock,
    CiteSources,
    CodeDiffBlock,
    ComparisonTableBlock,
    MindmapNode,
    PresentUI,
    QuizQuestion,
    ShowMindmap,
    ShowQuiz,
    SourceRef,
    StepItem,
    StepsBlock,
    SuggestFollowups,
)

logger = structlog.get_logger(__name__)

Intent = Literal["ask", "summarize", "mindmap", "mcq", "other"]
RouteNode = Literal["qa_rag", "summarize", "mindmap", "quiz_intro", "code_mentor"]

# Composer chip id (contract 4.4) -> node. First recognised chip wins.
REQUESTED_TOOL_ROUTES: dict[str, RouteNode] = {
    "generate-questions": "quiz_intro",
    "mindmap": "mindmap",
}

# Metadata read by ag-ui-langgraph (agent.py, OnChatModelStream handler):
# chat-model calls carrying it are NOT streamed to the client.
INTERNAL_LLM_CONFIG: RunnableConfig = {
    "metadata": {"emit-messages": False, "emit-tool-calls": False},
    "tags": ["mentor:internal"],
}

# Resume sentinels produced by ag-ui-langgraph when RunAgentInput.resume is
# used (ag_ui_langgraph/interrupts.py, verified on 0.0.47).
AGUI_CANCELLED = "__agui_cancelled__"
AGUI_RESUME_MAP = "__agui_resume_map__"

# ---------------------------------------------------------------------------
# Chat model hook
# ---------------------------------------------------------------------------

ChatModelFactory = Callable[[], BaseChatModel]
_chat_model_factory: ChatModelFactory | None = None


def set_chat_model_factory(factory: ChatModelFactory | None) -> None:
    """Plug the real streaming chat model in (e.g. at app startup).

    TODO(LLM): e.g. ``set_chat_model_factory(lambda: init_chat_model(
    "openai:gpt-4.1-mini", streaming=True))``. With ``None`` the graph uses
    the placeholders below.
    """
    global _chat_model_factory
    _chat_model_factory = factory


def get_chat_model() -> BaseChatModel | None:
    return _chat_model_factory() if _chat_model_factory else None


def _merge_config(config: RunnableConfig, extra: RunnableConfig) -> RunnableConfig:
    merged: dict[str, Any] = dict(config or {})
    merged["metadata"] = {**(config or {}).get("metadata", {}), **extra.get("metadata", {})}
    merged["tags"] = [*(config or {}).get("tags", []), *extra.get("tags", [])]
    return merged  # type: ignore[return-value]


async def _placeholder_stream(text: str, config: RunnableConfig) -> AIMessage:
    """Stream ``text`` like a chat model would (placeholder only)."""
    return await stream_text(text, config)


# ---------------------------------------------------------------------------
# LLM / retrieval touch points (TODO)
# ---------------------------------------------------------------------------


class RetrievedChunk(TypedDict):
    file_id: str
    file_name: str
    page: int | None
    text: str


async def llm_classify_intent(
    question: str, history: Sequence[BaseMessage], config: RunnableConfig
) -> Intent:
    """Classify the latest user message.

    Input:  ``question`` (latest user text), ``history`` (previous messages,
            for follow-ups like "làm tiếp đi").
    Output: one of ``"ask" | "summarize" | "mindmap" | "mcq" | "other"``.

    TODO(LLM): ``model.with_structured_output(IntentOut).ainvoke(msgs,
    _merge_config(config, INTERNAL_LLM_CONFIG))`` where ``IntentOut`` is
    ``{intent: Intent}``. INTERNAL_LLM_CONFIG is mandatory: structured output
    is a tool call under the hood and would otherwise reach the client as an
    unknown tool. Placeholder: keyword heuristics.
    """
    q = question.lower()
    if re.search(r"tóm tắt|summar", q):
        return "summarize"
    if re.search(r"mindmap|sơ đồ", q):
        return "mindmap"
    if re.search(r"quiz|câu hỏi|kiểm tra|trắc nghiệm", q):
        return "mcq"
    if re.search(r"\?|là gì|tại sao|giải thích|thế nào", q):
        return "ask"
    return "other"


async def retrieve_chunks(question: str, document_ids: Sequence[str]) -> list[RetrievedChunk]:
    """Retrieve passages from the session's active documents.

    Input:  ``question``, ``document_ids`` (from context ``active_document_ids``).
    Output: top-k ``RetrievedChunk`` (file_id, file_name, page or None, text).

    TODO(RAG): call the existing vector store used by /upload + /session-files.
    Placeholder: one fake chunk per document id.
    """
    return [
        {
            "file_id": doc_id,
            "file_name": f"{doc_id}.pdf",
            "page": 1,
            "text": "Đa hình cho phép cùng một lời gọi phương thức chạy cài đặt khác nhau tùy kiểu thực của đối tượng.",
        }
        for doc_id in list(document_ids)[:2]
    ]


async def llm_stream_answer(
    system_prompt: str, messages: Sequence[BaseMessage], config: RunnableConfig, *, placeholder: str
) -> AIMessage:
    """Stream an assistant answer to the client (TEXT_MESSAGE_*).

    Input:  system prompt, conversation messages (LangChain), node ``config``.
    Output: the final ``AIMessage`` (append it to state).

    Real path: ``await model.ainvoke([SystemMessage(...), *messages], config)``.
    Passing the node config is enough for ag-ui-langgraph to stream tokens.
    """
    model = get_chat_model()
    if model is None:
        return await _placeholder_stream(placeholder, config)
    result = await model.ainvoke([SystemMessage(content=system_prompt), *messages], config)
    return AIMessage(id=result.id, content=message_text(result))


async def llm_suggest_followups(question: str, answer: str, config: RunnableConfig) -> list[str]:
    """Input: latest question + answer text. Output: <= 3 short Vietnamese questions.

    TODO(LLM): structured output ``SuggestFollowups`` with INTERNAL_LLM_CONFIG.
    """
    return [
        "Đa hình lúc biên dịch khác gì đa hình lúc chạy?",
        "Cho ví dụ đa hình với interface trong Java?",
        "Ghi đè (override) và nạp chồng (overload) khác nhau thế nào?",
    ]


async def llm_generate_quiz(
    topic: str, chunks: Sequence[RetrievedChunk], count: int, difficulty: str, config: RunnableConfig
) -> ShowQuiz:
    """Input: topic text, retrieved chunks, ``count`` (1..30), ``difficulty``.
    Output: ``ShowQuiz`` with exactly ``count`` questions (validated).

    TODO(LLM): structured output ``ShowQuiz`` with INTERNAL_LLM_CONFIG, then
    re-validate (``ShowQuiz.model_validate``) and retry on ValidationError.
    """
    bank = [
        ("Từ khóa nào dùng để kế thừa một lớp trong Java?", ["implements", "extends", "inherits", "super"], 1,
         "Lớp con dùng `extends` để kế thừa lớp cha; `implements` dành cho interface."),
        ("Tính đóng gói (encapsulation) chủ yếu đạt được bằng cách nào?", ["Dùng static", "Dùng private + getter/setter", "Dùng final", "Dùng abstract"], 1,
         "Ẩn trạng thái bằng `private` và chỉ mở qua phương thức công khai."),
        ("Đa hình lúc chạy trong Java dựa trên cơ chế nào?", ["Nạp chồng", "Ghi đè + liên kết động", "Generic", "Annotation"], 1,
         "JVM chọn phương thức ghi đè theo kiểu thực của đối tượng lúc chạy."),
        ("Lớp trừu tượng (abstract class) có thể làm gì mà interface (trước Java 8) không làm được?", ["Có hàm khởi tạo và trường thể hiện", "Đa kế thừa", "Khai báo hằng", "Được new trực tiếp"], 0,
         "Abstract class có constructor và trường thể hiện; interface thì không."),
        ("Phát biểu nào đúng về `final` trên một phương thức?", ["Không thể gọi", "Không thể ghi đè", "Không thể nạp chồng", "Bắt buộc static"], 1,
         "Phương thức `final` không thể bị lớp con ghi đè."),
    ]
    level = difficulty if difficulty in ("easy", "medium", "hard") else "medium"
    questions = []
    for i in range(count):
        text, options, answer, explanation = bank[i % len(bank)]
        suffix = f" (biến thể {i // len(bank) + 1})" if i >= len(bank) else ""
        questions.append(
            QuizQuestion(
                id=f"q{i + 1}", question=f"Câu {i + 1}: {text}{suffix}", options=list(options),
                answer_index=answer, explanation=explanation, difficulty=level,  # type: ignore[arg-type]
            )
        )
    return ShowQuiz(title="Ôn tập lập trình hướng đối tượng", questions=questions)


async def llm_generate_mindmap(topic: str, chunks: Sequence[RetrievedChunk], config: RunnableConfig) -> ShowMindmap:
    """Input: topic text + retrieved chunks. Output: ``ShowMindmap`` (depth <= 6).

    TODO(LLM): summarization -> concept hierarchy (event-driven-architecture
    .drawio, Mind Map Module), structured output with INTERNAL_LLM_CONFIG.
    """
    def node(node_id: str, label: str, *children: MindmapNode) -> MindmapNode:
        return MindmapNode(id=node_id, label=label, children=list(children) or None)

    root = node(
        "root", "Lập trình hướng đối tượng",
        node("enc", "Đóng gói", node("enc1", "private + getter/setter"), node("enc2", "Ẩn chi tiết cài đặt")),
        node("inh", "Kế thừa", node("inh1", "extends"), node("inh2", "super"), node("inh3", "Ghi đè phương thức")),
        node("pol", "Đa hình", node("pol1", "Nạp chồng (compile-time)"), node("pol2", "Ghi đè (runtime)")),
        node("abs", "Trừu tượng", node("abs1", "abstract class"), node("abs2", "interface")),
    )
    return ShowMindmap(title="Sơ đồ tư duy: OOP", root=root)


# ---------------------------------------------------------------------------
# Shared-state helper
# ---------------------------------------------------------------------------


async def publish_shared_state(
    artifacts: Mapping[str, Any], jobs: Mapping[str, Any], config: RunnableConfig
) -> None:
    """Push artifacts/jobs to the client mid-node (STATE_SNAPSHOT).

    Uses ag-ui-langgraph's ``manually_emit_state`` custom event (verified on
    0.0.47: CustomEventNames.ManuallyEmitState -> StateSnapshotEvent). The
    node must still *return* the same values so the checkpointer stores them.
    """
    await adispatch_custom_event(
        "manually_emit_state",
        shared_state({"artifacts": dict(artifacts), "jobs": dict(jobs)}),
        config=config,
    )


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

MENTOR_PROMPT = (
    "Bạn là trợ lý lập trình (Mentor Code). Trả lời bằng tiếng Việt, ngắn gọn, "
    "có ví dụ code khi cần. Dùng Markdown, công thức trong $...$."
)


async def router(state: MentorState, config: RunnableConfig) -> Command[RouteNode]:
    # Priority (contract 4.4 / mock table): a resume never reaches the router
    # (LangGraph resumes the interrupted node), so the composer chips come
    # first and beat any intent classification.
    for tool_id in state.get("requested_tools") or []:
        if tool_id in REQUESTED_TOOL_ROUTES:
            target = REQUESTED_TOOL_ROUTES[tool_id]
            return Command(goto=target, update={"route": target})

    question = latest_user_text(state) or ""
    intent = await llm_classify_intent(question, state.get("messages") or [], config)
    has_docs = bool(state.get("active_document_ids"))
    target: RouteNode
    if intent == "summarize":
        target = "summarize"
    elif intent == "mindmap":
        target = "mindmap"
    elif intent == "mcq":
        target = "quiz_intro"
    elif intent == "ask" and has_docs:
        target = "qa_rag"
    else:  # "ask" without documents, "other"
        target = "code_mentor"
    return Command(goto=target, update={"route": target})


async def qa_rag(state: MentorState, config: RunnableConfig) -> dict[str, Any]:
    question = latest_user_text(state) or ""
    chunks = await retrieve_chunks(question, state.get("active_document_ids") or [])
    context = "\n\n".join(f"[{c['file_name']} tr.{c['page']}] {c['text']}" for c in chunks)
    answer = await llm_stream_answer(
        f"{MENTOR_PROMPT}\nChỉ dùng thông tin trong tài liệu sau:\n{context}",
        state["messages"],
        config,
        placeholder=(
            "**Đa hình** (polymorphism) cho phép cùng một lời gọi chạy cài đặt khác nhau. "
            "Gọi phương thức ảo qua bảng phương thức có chi phí $O(1)$.\n\n"
            "```java\nAnimal a = new Dog();\na.speak(); // Gâu gâu\n```"
        ),
    )
    calls: list[Any] = []
    if chunks:
        calls.append(("cite_sources", CiteSources(sources=[
            SourceRef(file_id=c["file_id"], file_name=c["file_name"], page=c["page"], quote=c["text"][:300])
            for c in chunks
        ])))
    followups = await llm_suggest_followups(question, message_text(answer), config)
    if followups:
        calls.append(("suggest_followups", SuggestFollowups(questions=followups[:3])))
    return {"messages": await stream_ui_tool_calls(calls, config, attach_to=answer)}


async def summarize(state: MentorState, config: RunnableConfig) -> dict[str, Any]:
    question = latest_user_text(state) or ""
    chunks = await retrieve_chunks(question, state.get("active_document_ids") or [])
    context = "\n\n".join(c["text"] for c in chunks)
    # TODO(LLM): multi-level summary (short/medium/long) as in the Summarization module.
    answer = await llm_stream_answer(
        f"{MENTOR_PROMPT}\nTóm tắt tài liệu sau thành các ý chính:\n{context}",
        state["messages"],
        config,
        placeholder="**Tóm tắt:**\n\n- Đóng gói\n- Kế thừa\n- Đa hình\n- Trừu tượng",
    )
    calls: list[Any] = []
    if chunks:
        calls.append(("cite_sources", CiteSources(sources=[
            SourceRef(file_id=c["file_id"], file_name=c["file_name"], page=c["page"], quote=c["text"][:300])
            for c in chunks
        ])))
    return {"messages": await stream_ui_tool_calls(calls, config, attach_to=answer)}


async def mindmap(state: MentorState, config: RunnableConfig) -> dict[str, Any]:
    artifacts = read_artifacts(state)
    jobs = read_jobs(state)
    job_id = new_id("job")
    jobs[job_id] = make_job("mindmap", "Đang vẽ sơ đồ tư duy", 0, "running")
    await publish_shared_state(artifacts, jobs, config)

    question = latest_user_text(state) or ""
    try:
        chunks = await retrieve_chunks(question, state.get("active_document_ids") or [])
        result = await llm_generate_mindmap(question, chunks, config)
    except (ValidationError, ValueError) as exc:
        logger.warning(f"mindmap generation failed: {exc}")
        jobs[job_id] = make_job("mindmap", "Vẽ sơ đồ tư duy thất bại", 100, "error")
        await publish_shared_state(artifacts, jobs, config)
        failed = await llm_stream_answer(MENTOR_PROMPT, state["messages"], config,
                                         placeholder="Xin lỗi, mình chưa vẽ được sơ đồ tư duy. Bạn thử lại nhé.")
        return {"messages": [failed], "artifacts": artifacts, "jobs": jobs}

    intro = await llm_stream_answer(MENTOR_PROMPT, state["messages"], config,
                                    placeholder="Đây là sơ đồ tư duy cho chủ đề bạn yêu cầu:")
    messages = await stream_ui_tool_calls([("show_mindmap", result)], config, attach_to=intro)
    artifacts["mindmaps"].append({"id": new_id("mindmap"), "title": result.title})
    jobs[job_id] = make_job("mindmap", "Đã vẽ sơ đồ tư duy", 100, "done")
    await publish_shared_state(artifacts, jobs, config)
    return {"messages": messages, "artifacts": artifacts, "jobs": jobs}


class QuizConfigPayload(BaseModel):
    """Resume payload of the ``quiz_config`` interrupt (contract 4.6)."""

    count: int = Field(default=10, ge=1, le=30)
    difficulty: Literal["easy", "medium", "hard"] = "medium"


QUIZ_DEFAULTS = {"count": 10, "difficulty": "medium"}


async def quiz_intro(state: MentorState, config: RunnableConfig) -> dict[str, Any]:
    """Assistant text BEFORE the interrupt (contract 4.6).

    Kept in its own node on purpose: a node that calls ``interrupt()`` is
    re-executed from the top on resume, so any text it streamed before the
    interrupt would be streamed (and paid for) twice.
    """
    intro = await llm_stream_answer(MENTOR_PROMPT, state["messages"], config,
                                    placeholder="Mình sẽ sinh câu hỏi trắc nghiệm. Bạn chọn số câu và độ khó nhé.")
    return {"messages": [intro]}


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


async def quiz(state: MentorState, config: RunnableConfig) -> Command[Literal["router", "__end__"]]:
    """Ask for quiz_config, then generate. Resume outcomes (contract 4.6):

    * resolved                     -> generate (even if a new user message came too)
    * cancelled, no new message    -> "Đã hủy sinh câu hỏi."
    * cancelled + new user message -> steer away: route the new message again

    "New user message" = id never seen in this thread's checkpoint. That test
    is done in server.py (MentorLangGraphAgent.prepare_stream), which adds such
    messages to state through ``Command(resume=..., update={"messages": ...})``
    because ag-ui-langgraph 0.0.47 drops them on the resume path. Here it
    therefore shows up as the last message of the state.
    """
    # Must be the first statement: a resumed node re-runs from the top, so
    # anything before interrupt() would run twice.
    answer = interrupt(
        {
            "reason": "input_required",
            "message": "Sinh câu hỏi từ tài liệu đang bật?",
            "metadata": {
                "kind": "quiz_config",
                "defaults": dict(QUIZ_DEFAULTS),
                # TODO(contract): item shape of "documents" is not defined in 4.6.
                "documents": [],
            },
        }
    )
    cfg = _parse_quiz_resume(answer)

    if cfg is None:
        messages = state.get("messages") or []
        if messages and isinstance(messages[-1], HumanMessage):
            # Steer away (useAgUiSteerAway, or a new message typed while the
            # form was open): drop the quiz and handle the new message.
            return Command(goto="router")
        cancelled = await llm_stream_answer(MENTOR_PROMPT, messages, config, placeholder="Đã hủy sinh câu hỏi.")
        return Command(goto=END, update={"messages": [cancelled]})

    artifacts = read_artifacts(state)
    jobs = read_jobs(state)
    job_id = new_id("job")
    jobs[job_id] = make_job("quiz", "Đang sinh câu hỏi", 0, "running")
    await publish_shared_state(artifacts, jobs, config)

    question = latest_user_text(state) or ""
    try:
        chunks = await retrieve_chunks(question, state.get("active_document_ids") or [])
        jobs[job_id] = make_job("quiz", "Đang sinh câu hỏi", 40, "running")
        await publish_shared_state(artifacts, jobs, config)
        result = await llm_generate_quiz(question, chunks, cfg.count, cfg.difficulty, config)
        jobs[job_id] = make_job("quiz", "Đang sinh câu hỏi", 80, "running")
        await publish_shared_state(artifacts, jobs, config)
    except (ValidationError, ValueError) as exc:
        logger.warning(f"quiz generation failed: {exc}")
        jobs[job_id] = make_job("quiz", "Sinh câu hỏi thất bại", 100, "error")
        await publish_shared_state(artifacts, jobs, config)
        failed = await llm_stream_answer(MENTOR_PROMPT, state["messages"], config,
                                         placeholder="Xin lỗi, mình chưa sinh được câu hỏi. Bạn thử lại nhé.")
        return Command(goto=END, update={"messages": [failed], "artifacts": artifacts, "jobs": jobs})

    # Attach to the quiz_intro message: the client resumes that interrupted
    # message, and live/snapshot/history then agree on one assistant message.
    intro = next((m for m in reversed(state.get("messages") or [])
                  if isinstance(m, AIMessage) and not m.tool_calls), None)
    messages = await stream_ui_tool_calls([("show_quiz", result)], config, attach_to=intro)
    # TODO(port): persist the quiz where /session-projects reads it and use that id.
    artifacts["quizzes"].append({"id": new_id("quiz"), "title": result.title, "count": len(result.questions)})
    jobs[job_id] = make_job("quiz", "Đã sinh câu hỏi", 100, "done")
    await publish_shared_state(artifacts, jobs, config)
    return Command(goto=END, update={"messages": messages, "artifacts": artifacts, "jobs": jobs})


def _placeholder_present_ui() -> PresentUI:
    return PresentUI(
        title="Abstract class và interface",
        blocks=[
            ComparisonTableBlock(
                type="comparison_table",
                columns=["Tiêu chí", "Abstract class", "Interface"],
                rows=[
                    ["Kế thừa", "Chỉ 1 lớp cha", "Nhiều interface"],
                    ["Trường thể hiện", "Có", "Không (chỉ hằng)"],
                    ["Constructor", "Có", "Không"],
                ],
                highlight_col=2,
            ),
            CalloutBlock(type="callout", tone="tip", title="Mẹo",
                         body_md="Ưu tiên **interface** để mô tả khả năng; dùng abstract class khi cần chia sẻ trạng thái."),
            CodeDiffBlock(
                type="code_diff", language="java",
                before="abstract class Shape { abstract double area(); }",
                after="interface Shape { double area(); }",
                explanation_md="Không có trạng thái chung nên chuyển sang `interface`.",
            ),
            StepsBlock(type="steps", items=[
                StepItem(title="Xác định hành vi chung", body_md="Liệt kê các phương thức."),
                StepItem(title="Có trạng thái chung?", body_md="Có thì dùng abstract class."),
                StepItem(title="Cài đặt", body_md="`implements` hoặc `extends`."),
            ]),
        ],
    )


async def code_mentor(state: MentorState, config: RunnableConfig) -> Command[Literal["ui_tools", "__end__"]]:
    """General programming mentor.

    Real path (pattern A): the model sees the UI tools and decides to call
    ``present_ui`` / ``suggest_followups``; tool-call chunks stream to the
    client with parentMessageId, then ``ui_tools`` (ToolNode) returns "ok".
    """
    model = get_chat_model()
    if model is not None:
        response = await model.bind_tools(UI_TOOLS).ainvoke(
            [SystemMessage(content=MENTOR_PROMPT), *state["messages"]], config
        )
        if getattr(response, "tool_calls", None):
            return Command(goto="ui_tools", update={"messages": [response]})
        return Command(goto=END, update={"messages": [response]})

    # Placeholder path (pattern B).
    question = (latest_user_text(state) or "").lower()
    calls: list[Any] = []
    if re.search(r"so sánh|khác|compare", question):
        text = await _placeholder_stream("So sánh nhanh **abstract class** và **interface**:", config)
        calls.append(("present_ui", _placeholder_present_ui()))
    else:
        text = await _placeholder_stream(
            "Mình là trợ lý lập trình. Hãy hỏi về OOP, Java hoặc đoạn code bạn đang viết.", config)
    calls.append(("suggest_followups", SuggestFollowups(
        questions=["Giải thích đa hình", "So sánh abstract class và interface", "Vẽ mindmap OOP"])))
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
    builder.add_edge("mindmap", END)
    builder.add_edge("quiz_intro", "quiz")
    builder.add_edge("ui_tools", END)
    return builder.compile(checkpointer=checkpointer)
