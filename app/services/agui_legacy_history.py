"""History of sessions created with the legacy WebSocket chat (BACKEND-PLAN GĐ4.1).

Those sessions have no AG-UI checkpoint. Their messages live in the legacy
graph's checkpoints (``CHECKPOINT_*`` database, default schema, same
``thread_id = session_uuid``), stored per question as::

    HumanMessage -> AIMessage(name="agent", tool_calls) -> ToolMessage(answer)

where the answer is ``{"message": "..."}`` JSON (answer/summary tools), plain
text (mind map / quiz tools) or ``Error: ...``. ``GET /threads/{id}/messages``
serves them as text-only user/assistant pairs with deterministic ids
(``legacy-{session}-{i}-u`` / ``-a``): the client echoes these ids on its next
run, which stores them once in the AG-UI checkpoint.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import structlog
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from app.core.config import settings

logger = structlog.get_logger(__name__)


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    parts = []
    for block in content or []:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("text", "")))
    return "".join(parts)


def _tool_answer(message: ToolMessage) -> str:
    text = _text(message.content).strip()
    if getattr(message, "status", None) == "error" or text.startswith("Error:"):
        return ""
    try:
        data = json.loads(text)
    except ValueError:
        return text
    if isinstance(data, dict) and isinstance(data.get("message"), str):
        return data["message"].strip()
    return text


def legacy_turns(messages: Sequence[BaseMessage]) -> list[tuple[str, str]]:
    """Legacy checkpoint messages -> ``(question, answer)`` per question ("" = no answer)."""
    turns: list[tuple[str, str]] = []
    for message in messages:
        if isinstance(message, HumanMessage):
            question = _text(message.content).strip()
            if question:
                turns.append((question, ""))
        elif turns and not turns[-1][1]:
            if isinstance(message, ToolMessage):
                answer = _tool_answer(message)
            elif isinstance(message, AIMessage) and not message.tool_calls:
                answer = _text(message.content).strip()
            else:
                answer = ""
            if answer:
                turns[-1] = (turns[-1][0], answer)
    return turns


def legacy_to_agui(session_id: str, messages: Sequence[BaseMessage]) -> list[dict[str, str]]:
    """Legacy checkpoint messages -> AG-UI text messages (one pair per question)."""
    out: list[dict[str, str]] = []
    for index, (question, answer) in enumerate(legacy_turns(messages)):
        out.append({"id": f"legacy-{session_id}-{index}-u", "role": "user", "content": question})
        if answer:
            out.append({"id": f"legacy-{session_id}-{index}-a", "role": "assistant", "content": answer})
    return out


async def read_legacy_messages(session_id: str) -> list[BaseMessage]:
    """Messages of the latest legacy checkpoint of ``session_id`` ([] if none)."""
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    async with AsyncPostgresSaver.from_conn_string(settings._checkpointer_db_uri) as saver:
        found = await saver.aget_tuple({"configurable": {"thread_id": session_id, "checkpoint_ns": ""}})
    if found is None:
        return []
    return list((found.checkpoint.get("channel_values") or {}).get("messages") or [])


async def legacy_history(session_id: str) -> list[dict[str, str]]:
    """AG-UI messages of a legacy session; [] when there is none or it cannot be read."""
    try:
        return legacy_to_agui(session_id, await read_legacy_messages(session_id))
    except Exception as exc:  # history must never break the page
        logger.warning(f"legacy history unavailable for {session_id}: {exc!r}")
        return []
