"""In-process event bus backing the SSE notify endpoint.

Agents publish progress events here; :mod:`app.api.v1.notify` drains the queue
per session. Kept out of the API layer so agents never import ``app.api``.
"""

import asyncio

sse_event_queues: dict[str, asyncio.Queue] = {}


def get_queue(session_id: str) -> asyncio.Queue:
    """Return (creating if needed) the event queue of a session."""
    if session_id not in sse_event_queues:
        sse_event_queues[session_id] = asyncio.Queue()
    return sse_event_queues[session_id]
