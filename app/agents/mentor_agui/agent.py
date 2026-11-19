"""``MentorLangGraphAgent``: ag-ui-langgraph's ``LangGraphAgent`` adapted to the
frontend contract (mentor-code-ui ``docs/agui/PLAN.md`` section 4).

Ported from mentor-code-ui ``backend-reference/agent/server.py``. Every override
below fixes a verified gap between ag-ui-langgraph 0.0.47 and the contract
(reference README section 8) and is exercised by ``scripts/agui_selfcheck.py``.
Several override protected/undocumented methods, so ag-ui-langgraph is pinned
exactly in pyproject.toml: re-run the self-check after any upgrade.
"""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from typing import Any

import structlog
from ag_ui.core import EventType, Interrupt, ResumeEntry, RunAgentInput, RunErrorEvent
from ag_ui_langgraph import LangGraphAgent
from ag_ui_langgraph.interrupts import lg_interrupt_to_agui

# Not in ag_ui_langgraph.__all__; it is the converter LangGraphAgent itself uses
# for RunAgentInput.messages, so reusing it keeps ids/content identical.
from ag_ui_langgraph.utils import agui_messages_to_langchain
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command

from .state import shared_state

logger = structlog.get_logger(__name__)

PUBLIC_ERROR_MESSAGE = "Trợ lý gặp lỗi khi xử lý yêu cầu. Bạn thử lại nhé."
DEFAULT_ERROR_CODE = "AGENT_ERROR"
KNOWN_REQUESTED_TOOLS = ("generate-questions", "mindmap")


# ---------------------------------------------------------------------------
# Context (contract 4.4): Context.value is always a JSON string
# ---------------------------------------------------------------------------


def _context_items(context: list[Any] | None) -> dict[str, str]:
    items: dict[str, str] = {}
    for entry in context or []:
        if isinstance(entry, Mapping):
            description, value = entry.get("description"), entry.get("value")
        else:
            description = getattr(entry, "description", None)
            value = getattr(entry, "value", None)
        if isinstance(description, str) and isinstance(value, str):
            items[description] = value
    return items


def _json_or(raw: str | None, default: Any) -> Any:
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        logger.warning(f"context value is not JSON: {raw[:200]!r}")
        return default


def parse_run_context(context: list[Any] | None) -> dict[str, Any]:
    """Context[] -> state keys.

    Always returns all three keys so a run without chips resets
    ``requested_tools`` left over from the previous run. Chip ids keep the
    order the user picked them in, without duplicates (several chips are
    processed one after the other, see ``graph.router``).
    """
    items = _context_items(context)
    tools = _json_or(items.get("requested_tools"), [])
    docs = _json_or(items.get("active_document_ids"), [])
    user = _json_or(items.get("user"), {})
    requested: list[str] = []
    if isinstance(tools, list):
        for tool_id in tools:
            if tool_id in KNOWN_REQUESTED_TOOLS and tool_id not in requested:
                requested.append(tool_id)
    return {
        "requested_tools": requested,
        "active_document_ids": [str(d) for d in docs] if isinstance(docs, list) else [],
        "user": user if isinstance(user, dict) else {},
    }


# ---------------------------------------------------------------------------
# Agent adapter
# ---------------------------------------------------------------------------


class MentorLangGraphAgent(LangGraphAgent):
    """LangGraphAgent + the contract adaptations.

    No new constructor arguments: ``add_langgraph_fastapi_endpoint`` calls
    ``LangGraphAgent.clone()`` once per request.
    """

    _steer_update: dict[str, Any] | None = None

    # (1) Contract 4.6: interrupt.metadata = {"kind": ..., "defaults": ..., ...}.
    # The default mapper nests the raw value under metadata["langgraph"].
    def _interrupts_to_agui(self, lg_interrupts) -> list[Interrupt]:
        out: list[Interrupt] = []
        for lg in lg_interrupts:
            mapped = lg_interrupt_to_agui(lg)
            raw = getattr(lg, "value", None)
            if isinstance(raw, Mapping) and isinstance(raw.get("metadata"), Mapping):
                mapped = mapped.model_copy(update={"metadata": dict(raw["metadata"])})
            out.append(mapped)
        return out

    # (2) Contract 4.7: STATE_SNAPSHOT carries exactly {artifacts, jobs}.
    # The default keeps every output-schema key, including `messages`.
    def get_state_snapshot(self, state: Mapping[str, Any]) -> dict[str, Any]:
        return shared_state(state or {})

    # (3) Contract 4.4: copy RunAgentInput.context into graph state keys, keep
    # the server-owned shared state out of client hands, and drop tool results
    # (or tool-call messages) the client echoes under an id we stored them
    # under a different id.
    def langgraph_default_merge_state(self, state, messages, input: RunAgentInput):
        merged = super().langgraph_default_merge_state(state, messages, input)
        merged.update(parse_run_context(input.context))
        merged.pop("artifacts", None)  # the server owns shared state
        merged.pop("jobs", None)

        stored = list(state.get("messages") or [])
        stored_ids = {getattr(m, "id", None) for m in stored}
        stored_results = {m.tool_call_id for m in stored if isinstance(m, ToolMessage)}
        stored_calls = {
            c.get("id") for m in stored if isinstance(m, AIMessage) for c in (m.tool_calls or [])
        }

        def already_stored(m) -> bool:
            if getattr(m, "id", None) in stored_ids:
                return False
            if isinstance(m, ToolMessage):
                return m.tool_call_id in stored_results
            if isinstance(m, AIMessage) and m.tool_calls:
                return all(c.get("id") in stored_calls for c in m.tool_calls)
            return False

        merged["messages"] = [m for m in merged.get("messages") or [] if not already_stored(m)]
        return merged

    # (4) New user message while an interrupt is open.
    #  a) useAgUiSteerAway sends resume=[cancelled] + the new message. The
    #     default resume path builds Command(resume=...) only, silently
    #     dropping the message; we add it via Command(update=...).
    #  b) No resume at all (e.g. after a page reload the form is gone): the
    #     default re-emits the old interrupt without running the graph and
    #     without an assistant text message. We cancel the open interrupt and
    #     answer the new message instead.
    #  c) resolved + a new message (standard clients do not send this): the
    #     message is stored but the resolved branch wins (contract 4.6).
    # "New" = id not present in the thread's checkpoint (contract 4.6).
    async def prepare_stream(self, input: RunAgentInput, agent_state, config):
        self._steer_update = None
        open_interrupts = [
            itr
            for task in (getattr(agent_state, "tasks", None) or ())
            for itr in (getattr(task, "interrupts", None) or ())
        ]
        if open_interrupts:
            checkpoint_ids = {
                getattr(m, "id", None) for m in (agent_state.values or {}).get("messages", [])
            }
            new_user_messages = [
                m
                for m in agui_messages_to_langchain(list(input.messages or []))
                if isinstance(m, HumanMessage) and m.id not in checkpoint_ids
            ]
            if new_user_messages:
                if not input.resume:
                    input = input.model_copy(
                        update={
                            "resume": [
                                ResumeEntry(interrupt_id=itr.id, status="cancelled")
                                for itr in open_interrupts
                            ]
                        }
                    )
                self._steer_update = {
                    "messages": new_user_messages,
                    **parse_run_context(input.context),
                }
        return await super().prepare_stream(input=input, agent_state=agent_state, config=config)

    def _build_command_from_agui_resume(self, entries, *, open_interrupts=None) -> Command:
        command = super()._build_command_from_agui_resume(entries, open_interrupts=open_interrupts)
        if self._steer_update:
            return Command(resume=command.resume, update=self._steer_update)
        return command

    # (5) RUN_ERROR {message, code}: never leak exception text to the browser.
    # Also one summary log record per run (BACKEND-PLAN GĐ4.4), written even
    # when the client disconnects (Stop button, closed tab).
    async def run(self, input: RunAgentInput):
        started = time.monotonic()
        nodes: list[str] = []
        end, error_code, interrupted = "CANCELLED", None, False
        try:
            async for event in super().run(input):
                kind = getattr(event, "type", None)
                if kind == EventType.STEP_STARTED:
                    name = getattr(event, "step_name", None)
                    if name and (not nodes or nodes[-1] != name):
                        nodes.append(name)
                elif kind == EventType.RUN_FINISHED:
                    end = "RUN_FINISHED"
                    interrupted = getattr(event, "outcome", None) is not None
                elif kind == EventType.RUN_ERROR:
                    logger.error(
                        f"agent run failed thread={input.thread_id} run={input.run_id}: "
                        f"{getattr(event, 'message', '')}"
                    )
                    event = RunErrorEvent(
                        type=EventType.RUN_ERROR,
                        message=PUBLIC_ERROR_MESSAGE,
                        code=getattr(event, "code", None) or DEFAULT_ERROR_CODE,
                    )
                    end, error_code = "RUN_ERROR", event.code
                yield event
        finally:
            logger.info(
                "agui run",
                thread_id=input.thread_id,
                run_id=input.run_id,
                resume=bool(input.resume),
                nodes=nodes,
                duration_ms=int((time.monotonic() - started) * 1000),
                end=end,
                error_code=error_code,
                interrupted=interrupted,
            )


def make_agent(graph) -> MentorLangGraphAgent:
    return MentorLangGraphAgent(
        name="mentor",
        graph=graph,
        description="Mentor Code: trợ lý học lập trình",
        emit_interrupt_outcome=True,  # RUN_FINISHED.outcome = {type:"interrupt", interrupts:[...]}
        enable_legacy_on_interrupt_event=False,  # no extra CUSTOM "on_interrupt" event
        emit_raw_events=False,  # no RAW events / raw_event copies (payload size)
    )
