from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import asyncio
import json

router = APIRouter()

sse_event_queues = {}


@router.get("/sse/notify")
async def sse_notify(request: Request, session_id: str):
    print(f"[SSE] Client connected: session_id={session_id}")
    if session_id not in sse_event_queues:
        sse_event_queues[session_id] = asyncio.Queue()
    queue = sse_event_queues[session_id]

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    print(f"[SSE] Client disconnected: session_id={session_id}")
                    break

                try:
                    # Tăng timeout lên 1000 giây (16.7 phút)
                    event = await asyncio.wait_for(queue.get(), timeout=1000)

                    if isinstance(event, dict):
                        yield f"data: {json.dumps(event)}\n\n"
                        if event.get("type") == "done":
                            break
                    elif event == "done":
                        yield f"data: {json.dumps({'type': 'done'})}\n\n"
                        break
                    else:
                        yield f"data: {event}\n\n"

                except asyncio.TimeoutError:
                    print(f"[SSE] Timeout for session_id={session_id}")
                    yield f"data: {json.dumps({'type': 'timeout', 'message': 'Connection timeout after 1000s'})}\n\n"
                    break
                except Exception as e:
                    print(f"[SSE] Error in queue.get(): {e}")
                    break
        finally:
            # Cleanup
            if session_id in sse_event_queues:
                del sse_event_queues[session_id]
                print(f"[SSE] Cleaned up queue for session_id={session_id}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
