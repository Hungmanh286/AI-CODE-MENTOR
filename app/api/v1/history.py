"""Chat history of the legacy WebSocket chat (``/chat/pedagogical``).

Read from the legacy graph's checkpoint (``CHECKPOINT_*`` database), the same
source as ``GET /threads/{id}/messages`` for legacy sessions. It used to be read
from Langfuse ``/api/public/sessions/{id}``, which Langfuse removed on 2026-11-16.
"""

import structlog
from fastapi import APIRouter

from app.services import agui_legacy_history

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get("/history-chat/{session_id}")
async def get_history_chat(session_id: str):
    try:
        messages = await agui_legacy_history.read_legacy_messages(session_id)
    except Exception as exc:
        logger.warning(f"history of {session_id} unavailable: {exc!r}")
        return {"error": "Không đọc được lịch sử trò chuyện."}
    turns = agui_legacy_history.legacy_turns(messages)
    return {
        "history": [
            {"index": index + 1, "question": question, "answer": answer or None}
            for index, (question, answer) in enumerate(turns)
        ]
    }
