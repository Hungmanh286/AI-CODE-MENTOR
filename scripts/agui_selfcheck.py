"""Offline self-check of the AG-UI agent (app/agents/mentor_agui) against the
frontend contract (mentor-code-ui docs/agui/PLAN.md section 4).

Ported from mentor-code-ui backend-reference/selfcheck.py. Runs the AG-UI
routes (lifespan, CORS, ag-ui-langgraph endpoint) in process with the
in-memory checkpointer and the placeholder LLM functions; no network, no
database, no API key. Re-run after upgrading ag-ui-langgraph:

    uv run python -m scripts.agui_selfcheck        # exit 1 on any FAIL
    uv run python -m scripts.agui_selfcheck -v     # also print event sequences

It also runs as a unit test (tests/unit/test_agui_selfcheck.py).

What it proves: the event mapping/ordering produced by ag-ui-langgraph for this
graph (4.8), tool args vs ui_catalog (4.5), interrupt/resume/steer-away (4.6),
STATE_SNAPSHOT shape (4.7), /threads history (4.3), CORS/health/400.
What it cannot prove: behaviour with a real LLM provider or Postgres, and how
the browser runtime renders it (that is the E2E checklist).
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import uuid
from typing import Any

import httpx  # noqa: E402
from langchain_core.language_models import BaseChatModel  # noqa: E402
from langchain_core.messages import AIMessage, AIMessageChunk  # noqa: E402
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult  # noqa: E402

from app.agents.mentor_agui import graph as graph_module  # noqa: E402
from app.agents.mentor_agui.agent import PUBLIC_ERROR_MESSAGE  # noqa: E402
from app.agents.mentor_agui.ui_catalog import TOOL_ARG_MODELS  # noqa: E402
from app.api.agui import create_standalone_app  # noqa: E402

agui_app = create_standalone_app()  # in-memory checkpointer, same CORS as main.py

VERBOSE = "-v" in sys.argv
RESULTS: list[tuple] = []
SEEN_MESSAGE_IDS: set = set()
SEEN_TOOL_CALL_IDS: set = set()
STANDARD_EXTRA_TYPES = {"STEP_STARTED", "STEP_FINISHED", "MESSAGES_SNAPSHOT", "CUSTOM", "RAW"}


def record(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and (not ok or VERBOSE) else ""))


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def user_msg(text: str) -> dict[str, Any]:
    return {"id": f"u_{uuid.uuid4().hex}", "role": "user", "content": text}


def ctx(requested_tools=None, docs=None) -> list[dict[str, str]]:
    return [
        {"description": "user", "value": json.dumps({"user_id": "u1", "user_name": "Hùng"})},
        {"description": "requested_tools", "value": json.dumps(requested_tools or [])},
        {"description": "active_document_ids", "value": json.dumps(docs or [])},
    ]


async def run_agent(client, thread_id, messages, context=None, resume=None, state=None):
    run_id = f"run_{uuid.uuid4().hex}"
    body = {
        "threadId": thread_id, "runId": run_id, "state": state or {}, "messages": messages,
        "tools": [], "context": context or ctx(), "forwardedProps": {},
    }
    if resume is not None:
        body["resume"] = resume
    resp = await client.post("/agent", json=body, headers={"accept": "text/event-stream"})
    assert resp.status_code == 200, (resp.status_code, resp.text[:300])
    assert resp.headers["content-type"].startswith("text/event-stream"), resp.headers["content-type"]
    events = []
    for chunk in resp.text.split("\n\n"):
        for line in chunk.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    if VERBOSE:
        print("   events:", " ".join(e["type"] for e in events))
    return run_id, events


# ---------------------------------------------------------------------------
# Contract 4.8 / 4.5 / 4.7 checker
# ---------------------------------------------------------------------------


def check_protocol(events, thread_id, run_id) -> list[str]:
    errs: list[str] = []
    if not events:
        return ["no events"]
    first, last = events[0], events[-1]
    if first["type"] != "RUN_STARTED" or first.get("threadId") != thread_id or first.get("runId") != run_id:
        errs.append(f"first event {first}")
    if last["type"] not in ("RUN_FINISHED", "RUN_ERROR"):
        errs.append(f"last event {last['type']}")
    terminals = [i for i, e in enumerate(events) if e["type"] in ("RUN_FINISHED", "RUN_ERROR")]
    if terminals != [len(events) - 1]:
        errs.append(f"terminal events at {terminals}")
    open_text: dict[str, bool] = {}
    open_tools: dict[str, str] = {}
    args: dict[str, str] = {}
    names: dict[str, str] = {}
    ended_tools: set = set()
    for e in events:
        t = e["type"]
        if t == "TEXT_MESSAGE_START":
            mid = e.get("messageId")
            if e.get("role") != "assistant":
                errs.append(f"TEXT_MESSAGE_START role {e.get('role')}")
            if mid in SEEN_MESSAGE_IDS:
                errs.append(f"message id reused {mid}")
            SEEN_MESSAGE_IDS.add(mid)
            open_text[mid] = True
        elif t == "TEXT_MESSAGE_CONTENT":
            if not open_text.get(e.get("messageId")):
                errs.append("CONTENT for closed/unknown message")
            if not e.get("delta"):
                errs.append("empty delta")
        elif t == "TEXT_MESSAGE_END":
            if not open_text.pop(e.get("messageId"), None):
                errs.append("END for unknown message")
        elif t == "TOOL_CALL_START":
            tid = e.get("toolCallId")
            if not tid or not e.get("toolCallName"):
                errs.append(f"bad TOOL_CALL_START {e}")
            if tid in SEEN_TOOL_CALL_IDS:
                errs.append(f"tool call id reused {tid}")
            SEEN_TOOL_CALL_IDS.add(tid)
            open_tools[tid] = e.get("toolCallName")
            names[tid] = e.get("toolCallName")
            args[tid] = ""
        elif t == "TOOL_CALL_ARGS":
            if e.get("toolCallId") not in open_tools:
                errs.append("ARGS for closed tool call")
            args[e.get("toolCallId")] = args.get(e.get("toolCallId"), "") + (e.get("delta") or "")
        elif t == "TOOL_CALL_END":
            tid = e.get("toolCallId")
            if tid not in open_tools:
                errs.append("END for unknown tool call")
            open_tools.pop(tid, None)
            ended_tools.add(tid)
            try:
                parsed = json.loads(args.get(tid) or "")
            except ValueError:
                errs.append(f"args of {tid} not JSON: {args.get(tid)!r:.120}")
                continue
            model = TOOL_ARG_MODELS.get(names.get(tid))
            if model is not None:
                try:
                    model.model_validate(parsed)
                except Exception as exc:  # pydantic.ValidationError
                    errs.append(f"{names.get(tid)} args invalid: {exc}")
        elif t == "TOOL_CALL_RESULT":
            if e.get("toolCallId") not in ended_tools or e.get("role") != "tool" or "messageId" not in e or "content" not in e:
                errs.append(f"bad TOOL_CALL_RESULT {e}")
        elif t == "STATE_SNAPSHOT":
            snap = e.get("snapshot")
            if not isinstance(snap, dict) or set(snap) != {"artifacts", "jobs"}:
                errs.append(f"snapshot keys {list(snap) if isinstance(snap, dict) else snap}")
            else:
                for job in snap["jobs"].values():
                    if job.get("status") not in ("running", "done", "error") or not isinstance(job.get("progress"), int) \
                            or not 0 <= job["progress"] <= 100:
                        errs.append(f"bad job {job}")
        elif t == "STATE_DELTA":
            for op in e.get("delta") or []:
                if op.get("op") not in ("add", "remove", "replace", "move", "copy", "test") or not str(op.get("path", "")).startswith("/"):
                    errs.append(f"bad patch op {op}")
        elif t in ("RUN_STARTED", "RUN_FINISHED", "RUN_ERROR") or t in STANDARD_EXTRA_TYPES:
            pass
        else:
            errs.append(f"unexpected event type {t}")
    if last["type"] == "RUN_FINISHED" and (open_text or open_tools):
        errs.append(f"unclosed at RUN_FINISHED text={list(open_text)} tools={list(open_tools)}")
    return errs


def of_type(events, t):
    return [e for e in events if e["type"] == t]


def tool_args(events, name) -> list[dict]:
    starts = {e["toolCallId"]: e for e in of_type(events, "TOOL_CALL_START") if e["toolCallName"] == name}
    out = []
    for tid in starts:
        out.append(json.loads("".join(e["delta"] for e in of_type(events, "TOOL_CALL_ARGS") if e["toolCallId"] == tid)))
    return out


def text_of(events) -> str:
    return "".join(e["delta"] for e in of_type(events, "TEXT_MESSAGE_CONTENT"))


def outcome(events) -> dict | None:
    last = events[-1] if events else {}
    return last.get("outcome") if last.get("type") == "RUN_FINISHED" else None


def last_snapshot(events) -> dict | None:
    snaps = of_type(events, "STATE_SNAPSHOT")
    return snaps[-1]["snapshot"] if snaps else None


# ---------------------------------------------------------------------------
# Fake chat model for pattern A (LLM-streamed tool calls) and internal calls
# ---------------------------------------------------------------------------


class FakeToolCallingModel(BaseChatModel):
    """Streams text; when tools are bound, then streams a present_ui tool call in pieces."""

    tools_bound: bool = False
    # Real providers (OpenAI, Anthropic) send the tool name with args "" first;
    # True = name and the first args piece in one chunk (e.g. one-shot providers).
    args_in_name_chunk: bool = False

    @property
    def _llm_type(self) -> str:
        return "fake-tool-calling"

    def bind_tools(self, tools, **kwargs):
        return self.model_copy(update={"tools_bound": True})

    def _chunks(self):
        msg_id = f"lc_fake_{uuid.uuid4().hex}"
        for token in ["Mình ", "so ", "sánh ", "nhé:"]:
            yield AIMessageChunk(content=token, id=msg_id)
        if self.tools_bound:
            payload = json.dumps({"title": "A vs I", "blocks": [
                {"type": "callout", "tone": "info", "title": "Ghi nhớ", "body_md": "Interface mô tả **khả năng**."}]})
            call_id = f"call_fake_{uuid.uuid4().hex}"
            pieces = [payload[:15], payload[15:40], payload[40:]]
            if not self.args_in_name_chunk:
                pieces = ["", *pieces]
            for i, piece in enumerate(pieces):
                yield AIMessageChunk(content="", id=msg_id, tool_call_chunks=[{
                    "name": "present_ui" if i == 0 else None, "args": piece,
                    "id": call_id if i == 0 else None, "index": 0, "type": "tool_call_chunk"}])

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        merged = None
        for c in self._chunks():
            merged = c if merged is None else merged + c
        return ChatResult(generations=[ChatGeneration(message=AIMessage(
            id=merged.id, content=merged.content, tool_calls=merged.tool_calls))])

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        for c in self._chunks():
            chunk = ChatGenerationChunk(message=c)
            yield chunk  # the base class fires on_llm_new_token itself


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


async def scenario(client, name, thread_id, messages, **kw):
    run_id, events = await run_agent(client, thread_id, messages, **kw)
    errs = check_protocol(events, thread_id, run_id)
    record(f"{name}: protocol 4.8/4.5/4.7", not errs, "; ".join(errs[:4]))
    return events


async def main() -> int:
    transport = httpx.ASGITransport(app=agui_app)
    async with agui_app.router.lifespan_context(agui_app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # --- HTTP basics -------------------------------------------------
            r = await client.get("/health")
            record("GET /health -> {ok:true}", r.status_code == 200 and r.json() == {"ok": True}, r.text)
            r = await client.options("/agent", headers={"origin": "http://localhost:3001", "access-control-request-method": "POST",
                                                        "access-control-request-headers": "content-type,authorization,accept"})
            hdr = {k.lower(): v for k, v in r.headers.items()}
            record("OPTIONS preflight -> 2xx + CORS headers (contract 4.3, relaxed at Gate 1)",
                   200 <= r.status_code < 300 and hdr.get("access-control-allow-origin") == "*"
                   and all(h in hdr.get("access-control-allow-headers", "") for h in ("content-type", "authorization", "accept")),
                   f"{r.status_code} {hdr}")
            r = await client.post("/agent", content=b"{not json", headers={"content-type": "application/json"})
            record("POST /agent bad JSON -> 400", r.status_code == 400, f"{r.status_code}")
            r = await client.get("/health", headers={"origin": "http://localhost:3001"})
            record("simple request has ACAO *", r.headers.get("access-control-allow-origin") == "*", str(dict(r.headers)))
            r = await client.get(f"/threads/{uuid.uuid4()}/messages")
            record("GET /threads/<new>/messages -> {messages:[]}", r.status_code == 200 and r.json() == {"messages": []}, r.text)

            # --- default (code_mentor, pattern B) ---------------------------
            t = str(uuid.uuid4())
            ev = await scenario(client, "default", t, [user_msg("xin chào")])
            record("default: text + suggest_followups(3)", bool(text_of(ev)) and len((tool_args(ev, "suggest_followups") or [{}])[0].get("questions", [])) == 3)
            starts = of_type(ev, "TOOL_CALL_START")
            text_ids = [e["messageId"] for e in of_type(ev, "TEXT_MESSAGE_START")]
            record("pattern B: TOOL_CALL_START.parentMessageId == the turn's text message id",
                   bool(starts) and len(text_ids) == 1 and all(s.get("parentMessageId") == text_ids[0] for s in starts),
                   f"{starts[:1]} {text_ids}")
            record("pattern B: TOOL_CALL_RESULT.content == 'ok'", all(e["content"] == "ok" for e in of_type(ev, "TOOL_CALL_RESULT")))
            extra = sorted({e["type"] for e in ev} & STANDARD_EXTRA_TYPES)
            record("extra standard event types present (not in 4.8, must be tolerated)", True, ",".join(extra))

            # --- second run on same thread: no duplicated messages ---------
            hist = (await client.get(f"/threads/{t}/messages")).json()["messages"]
            before = len(hist)
            await scenario(client, "default 2nd run (client echoes history)", t, hist + [user_msg("giải thích tiếp")])
            hist2 = (await client.get(f"/threads/{t}/messages")).json()["messages"]
            ids = [m["id"] for m in hist2]
            record("echoed history is not duplicated in checkpoint", len(ids) == len(set(ids)) and hist2[:before] == hist,
                   f"{before} -> {len(hist2)}")

            # --- second run with a transcript rebuilt from the STREAM ids ---
            # (what a client that ignores MESSAGES_SNAPSHOT would send)
            t2 = str(uuid.uuid4())
            u1 = user_msg("xin chào")
            ev = await scenario(client, "stream-transcript run 1", t2, [u1])
            transcript = [u1]
            by_parent: dict[str, dict] = {}
            for e in ev:
                if e["type"] == "TEXT_MESSAGE_START":
                    by_parent[e["messageId"]] = {"id": e["messageId"], "role": "assistant", "content": ""}
                    transcript.append(by_parent[e["messageId"]])
                elif e["type"] == "TEXT_MESSAGE_CONTENT":
                    by_parent[e["messageId"]]["content"] += e["delta"]
                elif e["type"] == "TOOL_CALL_START":
                    owner = by_parent.get(e.get("parentMessageId"))
                    if owner is None:
                        owner = {"id": e.get("parentMessageId") or e["toolCallId"], "role": "assistant"}
                        by_parent[owner["id"]] = owner
                        transcript.append(owner)
                    owner.setdefault("toolCalls", []).append({"id": e["toolCallId"], "type": "function",
                                                              "function": {"name": e["toolCallName"], "arguments": ""}})
                elif e["type"] == "TOOL_CALL_ARGS":
                    for m in by_parent.values():
                        for c in m.get("toolCalls", []):
                            if c["id"] == e["toolCallId"]:
                                c["function"]["arguments"] += e["delta"]
                elif e["type"] == "TOOL_CALL_RESULT":
                    transcript.append({"id": e["messageId"], "role": "tool", "toolCallId": e["toolCallId"], "content": e["content"]})
            n1 = len((await client.get(f"/threads/{t2}/messages")).json()["messages"])
            await scenario(client, "stream-transcript run 2", t2, transcript + [user_msg("giải thích tiếp")])
            h = (await client.get(f"/threads/{t2}/messages")).json()["messages"]
            tool_ids = [m["toolCallId"] for m in h if m["role"] == "tool"]
            record("transcript rebuilt from stream ids: no duplicated messages / tool results",
                   len(tool_ids) == len(set(tool_ids)) and len(h) == 2 * n1, f"{n1} -> {len(h)}; tool ids {tool_ids}")

            # --- qa_rag with documents ---------------------------------------
            ev = await scenario(client, "qa_rag", str(uuid.uuid4()), [user_msg("Giải thích đa hình là gì?")], context=ctx(docs=["doc1", "doc2"]))
            cites = tool_args(ev, "cite_sources")
            record("qa_rag: cite_sources with 2 sources", bool(cites) and len(cites[0]["sources"]) == 2, str(cites)[:200])

            # --- compare -> present_ui ---------------------------------------
            ev = await scenario(client, "compare", str(uuid.uuid4()), [user_msg("so sánh abstract class và interface")])
            pu = tool_args(ev, "present_ui")
            record("compare: present_ui with 4 blocks", bool(pu) and [b["type"] for b in pu[0]["blocks"]] == ["comparison_table", "callout", "code_diff", "steps"])

            # --- mindmap ------------------------------------------------------
            ev = await scenario(client, "mindmap", str(uuid.uuid4()), [user_msg("vẽ mindmap OOP")])
            snap = last_snapshot(ev) or {}
            record("mindmap: show_mindmap + artifacts.mindmaps + job done",
                   bool(tool_args(ev, "show_mindmap")) and len(snap.get("artifacts", {}).get("mindmaps", [])) == 1
                   and [j["status"] for j in snap.get("jobs", {}).values()] == ["done"], str(snap)[:200])

            # --- requested_tools -> mindmap ---------------------------------
            ev = await scenario(client, "requested_tools", str(uuid.uuid4()), [user_msg("abc")], context=ctx(requested_tools=["mindmap"]))
            record("requested_tools=['mindmap'] -> show_mindmap", bool(tool_args(ev, "show_mindmap")))

            # --- quiz: interrupt then resume resolved ------------------------
            tq = str(uuid.uuid4())
            ev = await scenario(client, "quiz interrupt", tq, [user_msg("tạo quiz")])
            oc = outcome(ev) or {}
            itr = (oc.get("interrupts") or [{}])[0]
            record("quiz: text message before interrupt", bool(of_type(ev, "TEXT_MESSAGE_START")))
            record("quiz: outcome.interrupt matches 4.6",
                   oc.get("type") == "interrupt" and itr.get("reason") == "input_required"
                   and itr.get("message") == "Sinh câu hỏi từ tài liệu đang bật?"
                   and itr.get("metadata") == {"kind": "quiz_config", "defaults": {"count": 10, "difficulty": "medium"}, "documents": []},
                   json.dumps(oc, ensure_ascii=False)[:300])
            record("quiz: no CUSTOM on_interrupt event", not any(e.get("name") == "on_interrupt" for e in of_type(ev, "CUSTOM")))
            hist = (await client.get(f"/threads/{tq}/messages")).json()["messages"]
            ev = await scenario(client, "quiz resume resolved", tq, hist,
                                resume=[{"interruptId": itr.get("id"), "status": "resolved", "payload": {"count": 3, "difficulty": "hard"}}])
            qs = tool_args(ev, "show_quiz")
            record("resume resolved {count:3}: show_quiz has exactly 3 questions (hard)",
                   bool(qs) and len(qs[0]["questions"]) == 3 and {q["difficulty"] for q in qs[0]["questions"]} == {"hard"})
            progress = [j["progress"] for s in of_type(ev, "STATE_SNAPSHOT") for j in s["snapshot"]["jobs"].values()]
            snap = last_snapshot(ev) or {}
            record("quiz: job progress 0->40->80->100 and artifacts.quizzes[count=3]",
                   [p for i, p in enumerate(progress) if i == 0 or p != progress[i - 1]][:4] == [0, 40, 80, 100]
                   and snap.get("artifacts", {}).get("quizzes", [{}])[0].get("count") == 3, f"{progress} {snap}")
            record("resume run: RUN_FINISHED without outcome", outcome(ev) is None)
            intro_ids = [m["id"] for m in hist if m["role"] == "assistant"]
            qstart = [s for s in of_type(ev, "TOOL_CALL_START") if s["toolCallName"] == "show_quiz"]
            record("show_quiz attached to the interrupted intro message (parentMessageId)",
                   len(qstart) == 1 and qstart[0].get("parentMessageId") == (intro_ids[-1] if intro_ids else None),
                   f"{qstart} {intro_ids}")
            snap_after_quiz = last_snapshot(ev)

            # --- history after quiz ------------------------------------------
            body = (await client.get(f"/threads/{tq}/messages")).json()
            hist = body["messages"]
            record("history: state = {artifacts, jobs} equal to the last STATE_SNAPSHOT (4.3/4.7)",
                   body.get("state") == snap_after_quiz and set(body.get("state") or {}) == {"artifacts", "jobs"},
                   json.dumps(body.get("state"), ensure_ascii=False)[:200])
            calls = [c for m in hist if m["role"] == "assistant" for c in m.get("toolCalls", [])]
            tools = [m for m in hist if m["role"] == "tool"]
            ok = any(c["function"]["name"] == "show_quiz" and isinstance(c["function"]["arguments"], str)
                     and len(json.loads(c["function"]["arguments"])["questions"]) == 3 for c in calls) \
                and {m["toolCallId"] for m in tools} == {c["id"] for c in calls} and all(c["type"] == "function" for c in calls)
            record("history: assistant toolCalls (JSON string args) + matching tool messages", ok, json.dumps(hist, ensure_ascii=False)[:300])
            from ag_ui_langgraph.utils import langchain_messages_to_agui
            st = await agui_app.state.agui_graph.aget_state({"configurable": {"thread_id": tq}})
            lib = [m.model_dump(mode="json", by_alias=True, exclude_none=True) for m in langchain_messages_to_agui(st.values["messages"])]
            lib_ids = [m["id"] for m in lib if m["role"] in ("user", "assistant", "tool")]
            record("history ids == ag-ui-langgraph converter ids", [m["id"] for m in hist] == lib_ids, f"{len(hist)} vs {len(lib_ids)}")

            # --- quiz cancelled ------------------------------------------------
            tc = str(uuid.uuid4())
            ev = await scenario(client, "cancel interrupt", tc, [user_msg("tạo quiz")])
            iid = ((outcome(ev) or {}).get("interrupts") or [{}])[0].get("id")
            hist = (await client.get(f"/threads/{tc}/messages")).json()["messages"]
            ev = await scenario(client, "resume cancelled", tc, hist, resume=[{"interruptId": iid, "status": "cancelled"}])
            record("resume cancelled: 'Đã hủy sinh câu hỏi.' and no show_quiz",
                   "Đã hủy sinh câu hỏi." in text_of(ev) and not tool_args(ev, "show_quiz"), text_of(ev))

            # --- steer away (resume cancelled + new user message) -----------
            ts = str(uuid.uuid4())
            ev = await scenario(client, "steer interrupt", ts, [user_msg("tạo quiz")])
            iid = ((outcome(ev) or {}).get("interrupts") or [{}])[0].get("id")
            hist = (await client.get(f"/threads/{ts}/messages")).json()["messages"]
            new_q = user_msg("so sánh abstract class và interface")
            ev = await scenario(client, "steer away", ts, hist + [new_q], resume=[{"interruptId": iid, "status": "cancelled"}])
            hist = (await client.get(f"/threads/{ts}/messages")).json()["messages"]
            record("steer away: new question answered (present_ui), no 'Đã hủy'",
                   bool(tool_args(ev, "present_ui")) and "Đã hủy" not in text_of(ev) and any(m["id"] == new_q["id"] for m in hist),
                   text_of(ev)[:120])

            # --- new message while interrupt open, no resume (after F5) -----
            tr = str(uuid.uuid4())
            ev = await scenario(client, "reload interrupt", tr, [user_msg("tạo quiz")])
            hist = (await client.get(f"/threads/{tr}/messages")).json()["messages"]
            ev = await scenario(client, "new message without resume", tr, hist + [user_msg("vẽ mindmap")])
            record("open interrupt + new message w/o resume: graph runs (show_mindmap), no replayed interrupt",
                   bool(tool_args(ev, "show_mindmap")) and outcome(ev) is None)

            # --- two threads in parallel ---------------------------------------
            ta, tb = str(uuid.uuid4()), str(uuid.uuid4())
            ma, mb = user_msg("vẽ mindmap"), user_msg("so sánh abstract class và interface")
            await asyncio.gather(run_agent(client, ta, [ma]), run_agent(client, tb, [mb]))
            ha = (await client.get(f"/threads/{ta}/messages")).json()["messages"]
            hb = (await client.get(f"/threads/{tb}/messages")).json()["messages"]
            names_a = {c["function"]["name"] for m in ha for c in m.get("toolCalls", [])}
            names_b = {c["function"]["name"] for m in hb for c in m.get("toolCalls", [])}
            record("parallel threads do not mix transcripts",
                   ha[0]["id"] == ma["id"] and hb[0]["id"] == mb["id"] and "show_mindmap" in names_a
                   and "present_ui" in names_b and "show_mindmap" not in names_b and "present_ui" not in names_a)

            # --- pattern A: LLM-streamed tool call + ToolNode ---------------
            graph_module.set_chat_model_factory(lambda: FakeToolCallingModel())
            try:
                ev = await scenario(client, "pattern A", str(uuid.uuid4()), [user_msg("so sánh A và B")])
            finally:
                graph_module.set_chat_model_factory(None)
            text_ids = {e["messageId"] for e in of_type(ev, "TEXT_MESSAGE_START")}
            starts = [s for s in of_type(ev, "TOOL_CALL_START") if s["toolCallName"] == "present_ui"]
            results = of_type(ev, "TOOL_CALL_RESULT")
            ta_hist = (await client.get(f"/threads/{ev[0]['threadId']}/messages")).json()["messages"]
            stored_tool_ids = {m["id"] for m in ta_hist if m["role"] == "tool"}
            record("pattern A: ToolNode result stored under TOOL_CALL_RESULT.messageId",
                   bool(results) and {r["messageId"] for r in results} == stored_tool_ids, f"{results} {stored_tool_ids}")
            record("pattern A: present_ui streamed with parentMessageId == text message id, RESULT 'ok'",
                   len(starts) == 1 and starts[0].get("parentMessageId") in text_ids
                   and len(of_type(ev, "TOOL_CALL_ARGS")) >= 2 and [r["content"] for r in results] == ["ok"],
                   f"starts={starts} text_ids={text_ids} results={results}")

            # Known ag-ui-langgraph 0.0.47 limitation: args carried by the same
            # chunk as the tool name are not emitted (the chunk only yields
            # TOOL_CALL_START). If this check FAILS after an upgrade, the
            # limitation is gone: update README ("Cần xác minh khi port").
            graph_module.set_chat_model_factory(lambda: FakeToolCallingModel(args_in_name_chunk=True))
            try:
                tid = str(uuid.uuid4())
                run_id, ev = await run_agent(client, tid, [user_msg("so sánh A và B")])
            finally:
                graph_module.set_chat_model_factory(None)
            got = "".join(e["delta"] for e in of_type(ev, "TOOL_CALL_ARGS"))
            record("known limitation still present: args in the tool-name chunk are dropped",
                   bool(got) and not got.startswith('{"title"'), repr(got[:40]))

            # --- INTERNAL_LLM_CONFIG hides internal model calls -------------
            original = graph_module.llm_classify_intent

            async def classify_with_internal_llm(question, history, config):
                await FakeToolCallingModel().ainvoke("x", graph_module._merge_config(config, graph_module.INTERNAL_LLM_CONFIG))
                return await original(question, history, config)

            graph_module.llm_classify_intent = classify_with_internal_llm
            try:
                ev = await scenario(client, "internal LLM call", str(uuid.uuid4()), [user_msg("xin chào")])
            finally:
                graph_module.llm_classify_intent = original
            record("INTERNAL_LLM_CONFIG: internal call emits no text", "Mình so sánh" not in text_of(ev)
                   and len(of_type(ev, "TEXT_MESSAGE_START")) == 1, text_of(ev)[:80])

            # --- RUN_ERROR ------------------------------------------------------
            original = graph_module.llm_classify_intent

            async def boom(question, history, config):
                raise RuntimeError("db password=secret leaked?")

            graph_module.llm_classify_intent = boom  # router looks it up at call time
            logging.disable(logging.CRITICAL)  # the expected traceback is not a failure
            try:
                tid = str(uuid.uuid4())
                run_id, ev = await run_agent(client, tid, [user_msg("xin chào")])
            finally:
                graph_module.llm_classify_intent = original
                logging.disable(logging.NOTSET)
            errs = check_protocol(ev, tid, run_id)
            last = ev[-1] if ev else {}
            record("node exception -> RUN_STARTED ... RUN_ERROR{message, code}, no leak",
                   not errs and last.get("type") == "RUN_ERROR" and last.get("message") == PUBLIC_ERROR_MESSAGE
                   and last.get("code") == "AGENT_ERROR" and "secret" not in json.dumps(ev), f"{errs} {last}")

    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
