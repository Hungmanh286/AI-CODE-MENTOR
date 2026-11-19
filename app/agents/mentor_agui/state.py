"""Graph state for the Mentor agent (docs/agui/PLAN.md, sections 4.4 and 4.7).

Shared state seen by the frontend (STATE_SNAPSHOT) is exactly::

    { "artifacts": { "quizzes": [...], "mindmaps": [...] },
      "jobs": { "<job_id>": { kind, label, progress, status } } }

Everything else in ``MentorState`` is server-side only. ``server.py`` trims the
snapshot to those two keys (``MentorLangGraphAgent.get_state_snapshot``), so
``messages``, ``requested_tools``... never leak into ``useAgUiState()``.
"""

from collections.abc import Mapping
from typing import Annotated, Any, Literal, NotRequired

from langchain_core.messages import AnyMessage
from langgraph.graph import MessagesState
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

# ---------------------------------------------------------------------------
# Shared state (contract 4.7)
# ---------------------------------------------------------------------------

JobStatus = Literal["running", "done", "error"]


class QuizArtifact(TypedDict):
    id: str
    title: str
    count: int


class MindmapArtifact(TypedDict):
    id: str
    title: str


class Artifacts(TypedDict):
    quizzes: list[QuizArtifact]
    mindmaps: list[MindmapArtifact]


class Job(TypedDict):
    kind: str  # "quiz" | "mindmap" | "document" ... (open string in the contract)
    label: str  # Vietnamese, shown in Studio, e.g. "Đang sinh câu hỏi"
    progress: int  # integer 0..100
    status: JobStatus


# ---------------------------------------------------------------------------
# Graph state
# ---------------------------------------------------------------------------


class MentorState(MessagesState):
    """Full graph state persisted by the checkpointer (thread_id = session uuid)."""

    # Shared with the frontend (4.7). NotRequired: a fresh thread has neither key
    # until a node writes it; read them through ``read_artifacts``/``read_jobs``.
    artifacts: NotRequired[Artifacts]
    jobs: NotRequired[dict[str, Job]]

    # Filled from RunAgentInput.context on every new run (4.4), see
    # MentorLangGraphAgent.langgraph_default_merge_state in server.py.
    requested_tools: NotRequired[list[str]]  # ["generate-questions" | "mindmap", ...]
    active_document_ids: NotRequired[list[str]]
    user: NotRequired[dict[str, Any]]  # {"user_id", "user_name"}; NOT an auth source

    # Internal routing result written by the router node.
    route: NotRequired[str]
    # Remaining composer-chip nodes of this run (several chips, see graph.router).
    pending_routes: NotRequired[list[str]]


class MentorInput(TypedDict):
    """Keys a client run is allowed to write into the graph.

    ``artifacts``/``jobs`` are deliberately absent: the frontend echoes its last
    known state in ``RunAgentInput.state`` and ag-ui-langgraph forwards every
    key that is in the graph *input* schema. Without this restriction a stale
    client copy would overwrite job progress written by the server.
    ``tools`` is accepted only because ag-ui-langgraph always forwards it (it
    is in its constant schema keys); the graph does not read it.
    """

    # Same reducer as MessagesState so both schemas describe one channel.
    messages: NotRequired[Annotated[list[AnyMessage], add_messages]]
    requested_tools: NotRequired[list[str]]
    active_document_ids: NotRequired[list[str]]
    user: NotRequired[dict[str, Any]]
    tools: NotRequired[list[Any]]


# ---------------------------------------------------------------------------
# Defensive readers (state from an old checkpoint may lack keys)
# ---------------------------------------------------------------------------


def read_artifacts(state: Mapping[str, Any]) -> Artifacts:
    raw = state.get("artifacts") or {}
    quizzes = raw.get("quizzes") if isinstance(raw, Mapping) else None
    mindmaps = raw.get("mindmaps") if isinstance(raw, Mapping) else None
    return {
        "quizzes": list(quizzes) if isinstance(quizzes, list) else [],
        "mindmaps": list(mindmaps) if isinstance(mindmaps, list) else [],
    }


def read_jobs(state: Mapping[str, Any]) -> dict[str, Job]:
    raw = state.get("jobs")
    return dict(raw) if isinstance(raw, Mapping) else {}


def shared_state(state: Mapping[str, Any]) -> dict[str, Any]:
    """The exact STATE_SNAPSHOT payload: always both keys, nothing else."""
    return {"artifacts": read_artifacts(state), "jobs": read_jobs(state)}


def make_job(kind: str, label: str, progress: int, status: JobStatus) -> Job:
    return {
        "kind": kind,
        "label": label,
        "progress": max(0, min(100, int(progress))),
        "status": status,
    }


def latest_user_text(state: Mapping[str, Any]) -> str | None:
    """Text of the most recent human message ('' parts joined), or None."""
    for message in reversed(state.get("messages") or []):
        if getattr(message, "type", None) == "human":
            return message_text(message)
    return None


def message_text(message: Any) -> str:
    """Plain text of a LangChain message whose content is str or content blocks."""
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content or []:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, Mapping) and block.get("type") == "text":
            parts.append(str(block.get("text", "")))
    return "".join(parts)
