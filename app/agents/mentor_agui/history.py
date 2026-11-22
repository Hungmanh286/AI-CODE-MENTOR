"""GET /threads/{thread_id}/messages: checkpointer messages -> AG-UI messages.

Contract (docs/agui/PLAN.md 4.3)::

    { "messages": AgUiMessage[], "state"?: { artifacts, jobs } }
    # unknown thread -> { "messages": [] }, never 404

``state`` is optional in the contract; this backend returns it (shape 4.7,
read from the checkpoint) so the frontend can restore Studio after F5.
Known MVP limit: a pending interrupt is not restored after F5 (server.py
cancels it when the next user message arrives).

* user:      { id, role: "user", content: str }
* assistant: { id, role: "assistant", content?: str,
               toolCalls?: [{ id, type: "function",
                              function: { name, arguments: <JSON string> } }] }
* tool:      { id, role: "tool", toolCallId, content: str }
* reasoning: { id, role: "reasoning", content: str }, right before the
             assistant message that reasoned (see reasoning.py for the id)

Ids are the checkpoint message ids unchanged. That matters: the frontend sends
these messages back on the next run and ag-ui-langgraph merges by id, so a
different id would append a duplicate to the graph state.

The converter is written against the contract instead of importing
``ag_ui_langgraph.utils.langchain_messages_to_agui`` (not part of the
package's public ``__all__``). selfcheck.py compares both on the same thread.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from .reasoning import reasoning_text
from .state import shared_state

# Placeholder text LangGraph/ag-ui-langgraph put in ToolMessages of tool calls
# that never finished (ag_ui_langgraph agent.py, _ORPHAN_TOOL_MSG_RE).
_ORPHAN_TOOL_MSG_RE = re.compile(r"^Tool call '.+' with id '.+' was interrupted before completion\.$")


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content or []:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, Mapping) and block.get("type") == "text":
            parts.append(str(block.get("text", "")))
    return "".join(parts)


def _tool_call_to_agui(call: Mapping[str, Any]) -> dict[str, Any]:
    args = call.get("args")
    arguments = args if isinstance(args, str) else json.dumps(args or {}, ensure_ascii=False)
    return {
        "id": str(call.get("id")),
        "type": "function",
        "function": {"name": str(call.get("name", "")), "arguments": arguments},
    }


def to_agui_messages(messages: Sequence[BaseMessage]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    known_tool_call_ids: set[str] = set()
    for message in messages:
        message_id = getattr(message, "id", None)
        if not message_id:
            continue  # add_messages always assigns ids; skip anything odd
        if isinstance(message, HumanMessage):
            out.append({"id": message_id, "role": "user", "content": _text(message.content)})
        elif isinstance(message, AIMessage):
            if isinstance(message.content, list):  # same order and ids as ag-ui-langgraph
                for index, block in enumerate(message.content):
                    if isinstance(block, Mapping) and block.get("type") == "reasoning":
                        thought = reasoning_text(block)
                        if thought:
                            out.append({
                                "id": str(block.get("id") or f"{message_id}-reasoning-{index}"),
                                "role": "reasoning",
                                "content": thought,
                            })
            text = _text(message.content)
            tool_calls = [c for c in (message.tool_calls or []) if c.get("id")]
            if not text and not tool_calls:
                continue
            entry: dict[str, Any] = {"id": message_id, "role": "assistant"}
            if text:
                entry["content"] = text
            if tool_calls:
                entry["toolCalls"] = [_tool_call_to_agui(c) for c in tool_calls]
                known_tool_call_ids.update(str(c["id"]) for c in tool_calls)
            out.append(entry)
        elif isinstance(message, ToolMessage):
            content = _text(message.content)
            if message.tool_call_id not in known_tool_call_ids or _ORPHAN_TOOL_MSG_RE.match(content):
                continue
            out.append(
                {"id": message_id, "role": "tool", "toolCallId": message.tool_call_id, "content": content}
            )
        # SystemMessage and others are not shown in the chat.
    return out


async def get_thread_messages(graph: Any, thread_id: str) -> dict[str, Any]:
    """Read the latest checkpoint of ``thread_id``.

    Unknown/empty thread -> exactly ``{"messages": []}``; otherwise
    ``{"messages": [...], "state": {"artifacts": ..., "jobs": ...}}``.
    """
    snapshot = await graph.aget_state({"configurable": {"thread_id": thread_id}})
    values: Mapping[str, Any] = getattr(snapshot, "values", None) or {}
    if not values:
        return {"messages": []}
    return {
        "messages": to_agui_messages(values.get("messages") or []),
        "state": shared_state(values),
    }
