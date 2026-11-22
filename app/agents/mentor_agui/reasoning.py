"""Reasoning ("đang suy nghĩ") of the answer model, streamed and stored under one id.

ChatOpenRouter with ``reasoning={...}`` streams the reasoning text in
``additional_kwargs["reasoning_content"]`` without any id. ag-ui-langgraph turns
it into REASONING_* events under a random id, while the history converters
(``history.to_agui_messages`` and ag-ui-langgraph's snapshot) name a stored
reasoning block by its ``id``. Different ids = the client shows the reasoning
twice (frontend README 9.7).

So the stream gets an id: before the first reasoning chunk,
``StableReasoningIds`` emits a text-less reasoning block carrying ``rs_<hex>``,
which ag-ui-langgraph adopts for the streamed message (its "pending reasoning
id"), and ``keep_reasoning`` stores the reasoning under that same id.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk

from .state import message_text


def _streamed_reasoning(message: Any) -> str:
    text = (getattr(message, "additional_kwargs", None) or {}).get("reasoning_content")
    return text if isinstance(text, str) else ""


class StableReasoningIds:
    """Mixin for a chat model that streams reasoning like ChatOpenRouter."""

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
        reasoning_id: str | None = None
        async for chunk in super()._astream(messages, stop=stop, run_manager=run_manager, **kwargs):
            if reasoning_id is None and _streamed_reasoning(chunk.message):
                reasoning_id = f"rs_{uuid.uuid4().hex}"
                yield ChatGenerationChunk(message=AIMessageChunk(
                    content=[{"type": "reasoning", "id": reasoning_id, "summary": []}],
                    id=chunk.message.id,
                ))
            yield chunk


def _reasoning_id(message: AIMessage) -> str | None:
    content = message.content if isinstance(message.content, list) else []
    for block in content:
        if isinstance(block, Mapping) and block.get("type") == "reasoning" and block.get("id"):
            return str(block["id"])
    return None


def keep_reasoning(message: AIMessage) -> AIMessage:
    """The answer to store: its text, preceded by its reasoning block if it reasoned.

    Content becomes ``[{"type": "reasoning", "id", "summary": [...]}, {"type": "text", ...}]``,
    the shape both history converters read. Without reasoning: plain text, as before.
    """
    text = message_text(message)
    reasoning = _streamed_reasoning(message)
    reasoning_id = _reasoning_id(message)
    if not reasoning or not reasoning_id:
        return message.model_copy(update={"content": text})
    block = {"type": "reasoning", "id": reasoning_id, "summary": [{"type": "summary_text", "text": reasoning}]}
    content: list[Any] = [block, {"type": "text", "text": text}] if text else [block]
    return message.model_copy(update={"content": content})


def reasoning_text(block: Mapping[str, Any]) -> str:
    """Text of a stored reasoning block (same rules as ag-ui-langgraph's snapshot)."""
    summary = block.get("summary")
    if isinstance(summary, list):
        parts = [s["text"] for s in summary if isinstance(s, Mapping) and isinstance(s.get("text"), str) and s["text"]]
        if parts:
            return "\n".join(parts)
    for key in ("reasoning", "text"):
        value = block.get(key)
        if isinstance(value, str) and value:
            return value
    return ""
