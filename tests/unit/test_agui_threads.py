"""GET /threads/{id}/messages projects stored artifacts into ``state`` (GĐ3.3)."""

import asyncio
import uuid

import httpx

from app.api.agui import create_standalone_app


class StorageOnlyBackend:
    chat_model_factory = None  # text stays on the placeholders

    def __init__(self):
        self.stored = {"quizzes": [{"id": "p9", "title": "Cũ", "count": 4}], "mindmaps": []}

    async def classify_intent(self, question, history, config):
        return "other"

    async def resolve_document_ids(self, session_id, client_ids):
        return []

    async def session_artifacts(self, session_id):
        return {k: list(v) for k, v in self.stored.items()}


def test_thread_history_state_reads_artifacts_from_storage():
    backend = StorageOnlyBackend()
    app = create_standalone_app(backend=backend)
    thread = str(uuid.uuid4())
    body = {
        "threadId": thread, "runId": f"run_{uuid.uuid4().hex}", "state": {}, "tools": [],
        "context": [], "forwardedProps": {},
        "messages": [{"id": f"u_{uuid.uuid4().hex}", "role": "user", "content": "xin chào"}],
    }

    async def go():
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                r = await client.post("/agent", json=body, headers={"accept": "text/event-stream"})
                assert r.status_code == 200 and "RUN_FINISHED" in r.text
                first = (await client.get(f"/threads/{thread}/messages")).json()
                backend.stored["mindmaps"].append({"id": "m2", "title": "Mới"})  # stored after the run
                second = (await client.get(f"/threads/{thread}/messages")).json()
                empty = (await client.get(f"/threads/{uuid.uuid4()}/messages")).json()
                return first, second, empty

    first, second, empty = asyncio.run(go())
    assert first["state"]["artifacts"]["quizzes"] == [{"id": "p9", "title": "Cũ", "count": 4}]
    assert second["state"]["artifacts"]["mindmaps"] == [{"id": "m2", "title": "Mới"}]
    assert empty == {"messages": []}  # unknown thread: contract 4.3, unchanged
