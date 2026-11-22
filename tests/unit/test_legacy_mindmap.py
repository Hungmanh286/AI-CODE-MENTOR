"""Mind map of the legacy WebSocket chat (summarizer graph, node ``mind_map``).

Seen live: OpenRouter 402 "You requested up to 65535 tokens" (no max_tokens), and
behind it the node read ``response.parts`` (Google genai SDK) from an OpenAI
ChatCompletion, sent a text model, and saved the image where no endpoint reads it.
The raw provider error (with the OpenRouter user id) was also pushed to the browser.
"""

import asyncio
import base64
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage

from app.agents.summarizer import graph as summarizer_graph
from app.core.config import settings

PNG = b"\x89PNG\r\n\x1a\nfake"


class _Completions:
    def __init__(self, images):
        self.images = images
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        message = SimpleNamespace(content="Sơ đồ", images=self.images)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


@pytest.fixture
def env(monkeypatch):
    uploads, rows = {}, []
    completions = _Completions(
        [{"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(PNG).decode()}}]
    )
    monkeypatch.setattr(summarizer_graph, "_openrouter_client",
                        lambda: SimpleNamespace(chat=SimpleNamespace(completions=completions)))
    monkeypatch.setattr(summarizer_graph, "minio_client",
                        SimpleNamespace(upload_data=lambda name, data: uploads.__setitem__(name, data) or True))
    monkeypatch.setattr(summarizer_graph, "create_mindmap", rows.append)
    monkeypatch.setattr(summarizer_graph, "generate_agent", SimpleNamespace(
        invoke=lambda *a, **k: {"messages": [AIMessage(content="Đã tạo sơ đồ tư duy.")]}))
    return completions, uploads, rows


def _run():
    return summarizer_graph.mind_map({"merge": "Ngoại lệ ..."}, {"configurable": {"thread_id": "s1"}})


def test_image_model_is_asked_for_an_image_with_capped_output(env):
    completions, _, _ = env
    _run()
    assert completions.kwargs["model"] == settings.MIND_MAP_IMAGE_MODEL
    assert completions.kwargs["max_tokens"] == settings.MIND_MAP_MAX_TOKENS
    assert completions.kwargs["extra_body"]["modalities"] == ["image", "text"]


def test_image_is_saved_where_the_endpoints_read_it(env):
    _, uploads, rows = env
    out = _run()
    assert uploads["s1/mindmap.png"] == PNG  # mindmap_done event + GET /get-mindmap
    (row,) = rows
    assert uploads[row.source_path] == PNG  # Studio list + GET /mindmap/{id}
    assert row.source_path == f"s1/{row.id}_mindmap.png"
    assert out["messages"][-1].content == "Đã tạo sơ đồ tư duy."


def test_no_image_in_the_answer_is_an_error_not_a_success(env):
    completions, uploads, rows = env
    completions.images = None
    with pytest.raises(RuntimeError):
        _run()
    assert uploads == {} and rows == []


def test_mindmap_url_endpoint_reads_the_saved_image_path(monkeypatch):
    from app.api.v1 import upload

    asked = []
    monkeypatch.setattr(upload, "minio_client", SimpleNamespace(
        file_exists=lambda p: asked.append(p) or True,
        get_presigned_url=lambda p, expiry_seconds: f"http://minio/{p}"))
    asyncio.run(upload.get_mindmap_url("s1"))
    assert asked == ["s1/mindmap.png"]


@pytest.mark.parametrize("tool_name", ["mindmap_tool", "question_generation_tool", "document_processing_tool"])
def test_tool_error_event_does_not_leak_provider_details(monkeypatch, tool_name):
    from app.agents.document_processing import tools
    from app.services.events import sse_event_queues

    async def boom(*a, **k):
        raise RuntimeError("Error code: 402 - {'user_id': 'user_secret'}")

    monkeypatch.setattr(tools.pdf_summarize_agent, "ainvoke", boom)
    monkeypatch.setattr(tools, "process_pdf", boom)

    async def go():
        queue = sse_event_queues.setdefault("s-err", asyncio.Queue())
        with pytest.raises(RuntimeError):
            await getattr(tools, tool_name).coroutine(query="x", config={"configurable": {"thread_id": "s-err"}})
        events = []
        while not queue.empty():
            events.append(queue.get_nowait())
        return events

    try:
        events = asyncio.run(go())
    finally:
        sse_event_queues.pop("s-err", None)
    errors = [e for e in events if isinstance(e, dict) and e["type"] == "error"]
    assert errors and "402" not in errors[0]["message"] and "user_secret" not in errors[0]["message"]
