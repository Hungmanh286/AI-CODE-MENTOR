from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import asyncio

router = APIRouter()

sse_event_queues = {}


@router.get("/sse/notify")
async def sse_notify(request: Request, session_id: str):
    print(f"[SSE] Client connected: session_id={session_id}")
    if session_id not in sse_event_queues:
        sse_event_queues[session_id] = asyncio.Queue()
    queue = sse_event_queues[session_id]

    async def event_generator():
        while True:
            if await request.is_disconnected():
                print(f"[SSE] Client disconnected: session_id={session_id}")
                break
            try:
                event = await queue.get()
                yield f"data: {event}\n\n"
            except Exception as e:
                print(f"[SSE] Error: {e}")
                break
        
        # Cleanup
        if session_id in sse_event_queues:
            del sse_event_queues[session_id]
            print(f"[SSE] Cleaned up queue for session_id={session_id}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")
