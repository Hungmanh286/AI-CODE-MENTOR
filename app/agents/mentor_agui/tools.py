"""The five backend UI tools of docs/agui/PLAN.md, section 4.5.

The tools do nothing server-side: their *arguments* are the UI payload that
the frontend renders (toolkit ``{ type: "backend", render }``), and their
result is always the string ``"ok"`` (TOOL_CALL_RESULT.content, contract 4.5).

How a tool call reaches the wire with ag-ui-langgraph 0.0.47 (all three were
observed in selfcheck.py / the source of ag_ui_langgraph/agent.py):

A. LLM-driven: ``llm.bind_tools(UI_TOOLS)``; the model streams tool-call
   chunks -> TOOL_CALL_START (parentMessageId = the AI message id) / ARGS /
   END, then ``ToolNode(UI_TOOLS)`` runs the tool -> TOOL_CALL_RESULT.
B. Deterministic, from a node: ``stream_ui_tool_calls`` below. It replays the
   tool calls through ``ScriptedMessageModel`` (a chat model that streams a
   pre-built message), i.e. exactly path A, then runs the tools. Result: same
   events as A, including parentMessageId, which contract 4.8 requires.
C. NOT used: invoking a tool directly inside a node (``tool.ainvoke(ToolCall)``)
   also streams START/ARGS/END/RESULT (from ``on_tool_end``) but WITHOUT
   parentMessageId, because ag-ui-langgraph only learns a call's owner from a
   chat-model event. Appending ``AIMessage(tool_calls=...)`` to state streams
   nothing at all; it only appears in the end-of-run MESSAGES_SNAPSHOT.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Iterator, Sequence
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel

from .ui_catalog import (
    CiteSources,
    PresentUI,
    ShowMindmap,
    ShowQuiz,
    SuggestFollowups,
    dump_args,
    validate_tool_args,
)

TOOL_RESULT_OK = "ok"


@tool("show_quiz", args_schema=ShowQuiz)
def show_quiz(**kwargs: Any) -> str:
    """Hiển thị bộ câu hỏi trắc nghiệm cho học viên làm ngay trong khung chat.

    Dùng khi người học muốn ôn tập hoặc kiểm tra kiến thức. Mỗi câu có đúng
    một đáp án đúng (answer_index tính từ 0) và lời giải thích ngắn.
    """
    return TOOL_RESULT_OK


@tool("show_mindmap", args_schema=ShowMindmap)
def show_mindmap(**kwargs: Any) -> str:
    """Hiển thị sơ đồ tư duy dạng cây (root -> children) cho một chủ đề."""
    return TOOL_RESULT_OK


@tool("cite_sources", args_schema=CiteSources)
def cite_sources(**kwargs: Any) -> str:
    """Trích dẫn đoạn tài liệu (file_id, file_name, page, quote) đã dùng để trả lời."""
    return TOOL_RESULT_OK


@tool("suggest_followups", args_schema=SuggestFollowups)
def suggest_followups(**kwargs: Any) -> str:
    """Gợi ý tối đa 3 câu hỏi tiếp theo ngắn gọn, viết bằng tiếng Việt."""
    return TOOL_RESULT_OK


@tool("present_ui", args_schema=PresentUI)
def present_ui(**kwargs: Any) -> str:
    """Trình bày nội dung bằng các khối UI: callout, steps, comparison_table,
    code_diff, concept_card. Dùng khi so sánh, hướng dẫn từng bước hoặc sửa code.
    """
    return TOOL_RESULT_OK


UI_TOOLS: list[BaseTool] = [show_quiz, show_mindmap, cite_sources, suggest_followups, present_ui]
UI_TOOLS_BY_NAME: dict[str, BaseTool] = {t.name: t for t in UI_TOOLS}


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def stable_tool_message_id(message: ToolMessage) -> ToolMessage:
    """Store a ToolMessage under the id the client saw in TOOL_CALL_RESULT.

    ag-ui-langgraph 0.0.47 emits ``TOOL_CALL_RESULT.messageId = tool_msg.id or
    tool_msg.tool_call_id``; tools return ToolMessages without id, so the
    client gets the tool_call_id, while add_messages would store a random
    uuid. The client echoes its transcript on the next run and ag-ui-langgraph
    merges by id, so the mismatch appended a duplicate tool message every turn
    (caught by scripts/agui-smoke.mjs). Pinning id = tool_call_id fixes it.
    """
    if not message.id:
        message.id = message.tool_call_id
    return message


async def _awrap_stable_id(request, execute):
    result = await execute(request)
    return stable_tool_message_id(result) if isinstance(result, ToolMessage) else result


def _wrap_stable_id(request, execute):
    result = execute(request)
    return stable_tool_message_id(result) if isinstance(result, ToolMessage) else result


def make_ui_tool_node():
    """``ToolNode(UI_TOOLS)`` for pattern A, with stable ToolMessage ids."""
    from langgraph.prebuilt import ToolNode

    return ToolNode(UI_TOOLS, name="ui_tools", wrap_tool_call=_wrap_stable_id, awrap_tool_call=_awrap_stable_id)


class ScriptedMessageModel(BaseChatModel):
    """Chat model that streams one pre-built assistant message.

    Used for deterministic output (and placeholders) so it travels the same
    path as real LLM output: on_chat_model_stream -> TEXT_MESSAGE_* and
    TOOL_CALL_START/ARGS/END with parentMessageId = ``message_id``.

    Each tool call starts with a chunk carrying name + id and EMPTY args, as
    OpenAI/Anthropic do: ag-ui-langgraph 0.0.47 does not emit args that come in
    the same chunk as the tool name (see README).
    The base class fires ``on_llm_new_token`` for every chunk; this class must
    not do it again.
    """

    message_id: str
    text: str = ""
    tool_calls: list[dict[str, Any]] = []  # [{"id", "name", "args": dict}]
    args_piece_size: int = 80

    @property
    def _llm_type(self) -> str:
        return "mentor-scripted-message"

    def _chunks(self) -> Iterator[AIMessageChunk]:
        chunks: list[AIMessageChunk] = []
        if self.text:
            words = self.text.split(" ")
            for i, word in enumerate(words):
                token = word if i == len(words) - 1 else word + " "
                if token:
                    chunks.append(AIMessageChunk(id=self.message_id, content=token))
        for index, call in enumerate(self.tool_calls):
            payload = json.dumps(call["args"], ensure_ascii=False)
            chunks.append(AIMessageChunk(id=self.message_id, content="", tool_call_chunks=[
                {"type": "tool_call_chunk", "index": index, "id": call["id"], "name": call["name"], "args": ""}]))
            for start in range(0, len(payload), self.args_piece_size):
                chunks.append(AIMessageChunk(id=self.message_id, content="", tool_call_chunks=[
                    {"type": "tool_call_chunk", "index": index, "id": None, "name": None,
                     "args": payload[start:start + self.args_piece_size]}]))
        if chunks:
            chunks[-1].chunk_position = "last"
        return iter(chunks)

    def _final_message(self) -> AIMessage:
        return AIMessage(
            id=self.message_id,
            content=self.text,
            tool_calls=[{"id": c["id"], "name": c["name"], "args": c["args"], "type": "tool_call"} for c in self.tool_calls],
        )

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=self._final_message())])

    def _stream(self, messages, stop=None, run_manager=None, **kwargs) -> Iterator[ChatGenerationChunk]:
        for chunk in self._chunks():
            yield ChatGenerationChunk(message=chunk)

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs) -> AsyncIterator[ChatGenerationChunk]:
        for chunk in self._chunks():
            yield ChatGenerationChunk(message=chunk)


async def stream_text(text: str, config: RunnableConfig) -> AIMessage:
    """Stream a fixed assistant text (TEXT_MESSAGE_*). Returns the AIMessage to store."""
    model = ScriptedMessageModel(message_id=new_id("msg"), text=text)
    await model.ainvoke([], config)
    return model._final_message()


UiCall = tuple[str, BaseModel | dict[str, Any]]


async def stream_ui_tool_calls(
    calls: Sequence[UiCall],
    config: RunnableConfig,
    *,
    attach_to: AIMessage | None = None,
) -> list[BaseMessage]:
    """Pattern B: stream UI tool calls from inside a node, then run them.

    Input:  ``calls`` = [(tool name, args model or dict), ...] (validated
            against ui_catalog), the node's ``config``, and optionally the
            assistant text message of the same turn (``attach_to``).
    Output: ``[AIMessage(tool_calls=...), ToolMessage("ok"), ...]`` to return
            from the node. With ``attach_to`` the AIMessage reuses its id and
            text, so ``add_messages`` replaces it in place: text + UI end up in
            ONE assistant message, live (parentMessageId = text message id), in
            MESSAGES_SNAPSHOT and in /threads/{id}/messages alike.
    """
    if not calls:
        return [attach_to] if attach_to is not None else []
    tool_calls: list[dict[str, Any]] = []
    for name, args in calls:
        if name not in UI_TOOLS_BY_NAME:
            raise ValueError(f"unknown UI tool: {name}")
        model = args if isinstance(args, BaseModel) else validate_tool_args(name, args)
        tool_calls.append({"id": new_id("call"), "name": name, "args": dump_args(model)})

    message_id = attach_to.id if attach_to is not None and attach_to.id else new_id("msg")
    await ScriptedMessageModel(message_id=message_id, tool_calls=tool_calls).ainvoke([], config)

    results: list[BaseMessage] = []
    for call in tool_calls:
        result = await UI_TOOLS_BY_NAME[call["name"]].ainvoke(
            {"type": "tool_call", "id": call["id"], "name": call["name"], "args": call["args"]}, config
        )
        if not isinstance(result, ToolMessage):  # defensive: a ToolCall input always yields a ToolMessage
            result = ToolMessage(content=TOOL_RESULT_OK, tool_call_id=call["id"], name=call["name"])
        results.append(stable_tool_message_id(result))

    merged = AIMessage(
        id=message_id,
        content=attach_to.content if attach_to is not None else "",
        tool_calls=[{"id": c["id"], "name": c["name"], "args": c["args"], "type": "tool_call"} for c in tool_calls],
    )
    return [merged, *results]
