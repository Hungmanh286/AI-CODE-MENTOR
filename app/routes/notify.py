import structlog

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import asyncio
import json

logger = structlog.get_logger(__name__)

router = APIRouter()

sse_event_queues = {}


@router.get("/sse/notify")
async def sse_notify(request: Request, session_id: str):
    logger.info(f"[SSE] Client connected: session_id={session_id}")
    if session_id not in sse_event_queues:
        sse_event_queues[session_id] = asyncio.Queue()
    queue = sse_event_queues[session_id]

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    logger.info(f"[SSE] Client disconnected: session_id={session_id}")
                    break

                try:
                    # Tăng timeout lên 1000 giây (16.7 phút)
                    event = await asyncio.wait_for(queue.get(), timeout=1000)

                    logger.info(f"[SSE] Event received for {session_id}: {event}")

                    if isinstance(event, dict):
                        event_json = json.dumps(event)
                        yield f"data: {event_json}\n\n"
                        logger.info(
                            f"[SSE] Sent dict event to {session_id}: {event_json}"
                        )

                        if event.get("type") == "done":
                            logger.info(
                                f"[SSE] ✅ 'done' event sent to client {session_id}, closing connection"
                            )
                            break
                    elif event == "done":
                        # Client expects: event.data === "done" (string, not JSON)
                        yield "data: done\n\n"
                        logger.info(
                            f"[SSE] ✅ String 'done' sent to client {session_id}, closing connection"
                        )
                        break
                    else:
                        yield f"data: {event}\n\n"
                        logger.info(f"[SSE] Sent raw event to {session_id}: {event}")

                except asyncio.TimeoutError:
                    logger.info(f"[SSE] Timeout for session_id={session_id}")
                    yield f"data: {json.dumps({'type': 'timeout', 'message': 'Connection timeout after 1000s'})}\n\n"
                    break
                except Exception as e:
                    logger.info(f"[SSE] Error in queue.get(): {e}")
                    break
        finally:
            # Cleanup
            if session_id in sse_event_queues:
                del sse_event_queues[session_id]
                logger.info(f"[SSE] Cleaned up queue for session_id={session_id}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
