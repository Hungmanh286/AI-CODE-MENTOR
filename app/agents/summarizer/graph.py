import base64
import uuid

import structlog
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_text_splitters import MarkdownHeaderTextSplitter
from langfuse.langchain import CallbackHandler
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import MessagesState

from app.agents.base import init_llm
from app.agents.common.prompts import Prompts
from app.agents.generator.graph import generate_agent
from app.core.config import settings
from app.core.paths import DATA_DIR
from app.db.datasource import get_active_file_id
from app.db.models.mindmap import MindMap
from app.infra.minio_client import minio_client
from app.services.mindmap_service import create_mindmap

logger = structlog.get_logger(__name__)


class QState(MessagesState):
    file_path: str | None
    chunk_size: int | None
    extractive_summaries: list[dict] | None
    summaries: list[dict] | None
    merge: str | None


tracer = CallbackHandler()


# Node 1: Tóm tắt từng chunk
def summarize_node(state: QState, config: RunnableConfig):
    summarize_chunks = []

    session_id = config["configurable"].get("thread_id")
    file_ids = get_active_file_id(session_id)

    chunk_size = 10
    for file_id in file_ids:
        docs_minio_path = f"{session_id}/{file_id}_docs.txt"

        if minio_client.file_exists(docs_minio_path):
            docs_data = minio_client.download_data(docs_minio_path)
            if docs_data:
                docs_content = docs_data.decode("utf-8")
                docs = [docs_content]

                splitter = MarkdownHeaderTextSplitter(
                    headers_to_split_on=[
                        ("#", "Header_1"),
                        ("##", "Header_2"),
                    ],
                )
                splits = [split for doc in docs for split in splitter.split_text(doc)]
                total_splits = len(splits)

                for i in range(0, total_splits, chunk_size):
                    chunk_text = "\n".join(
                        [split.page_content for split in splits[i : i + chunk_size]]
                    )
                    summarize_chunk = Prompts.SUMMARIZE_CHUNK_SUMMARY_PROMPT.format(
                        document=chunk_text
                    )

                    summarize_chunks.append(summarize_chunk)

    return {"summaries": summarize_chunks}


# Node 2: Extractive Summarization từng chunk
def extractive_node(state: QState, config: RunnableConfig):
    extractive_summaries = []
    chunk_size = 10
    session_id = config["configurable"].get("thread_id")
    file_ids = get_active_file_id(session_id)

    for file_id in file_ids:
        docs_minio_path = f"{session_id}/{file_id}_docs.txt"

        if minio_client.file_exists(docs_minio_path):
            docs_data = minio_client.download_data(docs_minio_path)
            if docs_data:
                docs_content = docs_data.decode("utf-8")
                docs = [docs_content]
            splitter = MarkdownHeaderTextSplitter(
                headers_to_split_on=[
                    ("#", "Header_1"),
                    ("##", "Header_2"),
                ],
            )
            splits = [split for doc in docs for split in splitter.split_text(doc)]

            total_splits = len(splits)

        for i in range(0, total_splits, chunk_size):
            chunk_text = "\n".join([split.page_content for split in splits[i : i + chunk_size]])
            extractive_chunk = Prompts.EXTRACTIVE_SUMMARIZE_PROMPT.format(chunk_text=chunk_text)

            extractive_summaries.append(extractive_chunk)

    return {"extractive_summaries": extractive_summaries}


llm = init_llm(
    model=settings.CHAT_MODEL,
    temperature=settings.CHAT_MODEL_TEMPERATURE_VISION,
    tags=["agent"],
)


# Node 3: Merge hai kết quả
def merge_node(state: QState, config: RunnableConfig):
    summaries = state["summaries"]
    extractive_summaries = state["extractive_summaries"]
    document = "\n".join([f"Chunk {i}:\n" + s for i, s in enumerate(summaries)])
    context = "\n".join([f"Chunk {i}:\n" + e for i, e in enumerate(extractive_summaries)])
    prompt = Prompts.Extract_Retrieve_Support_PROMPT.format(document=document, context=context)

    response_msg = llm.invoke(input=prompt, config=config)

    content = response_msg.content

    return {
        "merge": content,
    }


def _openrouter_client():
    from openai import OpenAI

    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=settings.OPENROUTER_API_KEY)


# Object read by the ``mindmap_done`` SSE event and GET /get-mindmap(-url): the latest one.
LATEST_MINDMAP = "{session_id}/mindmap.png"


def _first_image(message) -> bytes | None:
    """PNG bytes of the first image of an OpenRouter answer (``message.images``)."""
    for image in getattr(message, "images", None) or []:
        url = image.get("image_url", {}).get("url", "") if isinstance(image, dict) else image.image_url.url
        if url.startswith("data:") and "," in url:
            return base64.b64decode(url.split(",", 1)[1])
    return None


def mind_map(state: QState, config: RunnableConfig):
    """Draw the mind map as an image with an image model through OpenRouter."""
    merge = state.get("merge", "")
    session_id = config["configurable"].get("thread_id")

    response = _openrouter_client().chat.completions.create(
        model=settings.MIND_MAP_IMAGE_MODEL,
        messages=[{"role": "user", "content": Prompts.MIND_MAP_PROMPT.format(merge=merge)}],
        max_tokens=settings.MIND_MAP_MAX_TOKENS,
        extra_body={"modalities": ["image", "text"]},
    )
    image_bytes = _first_image(response.choices[0].message)
    if not image_bytes:
        raise RuntimeError(f"{settings.MIND_MAP_IMAGE_MODEL} returned no mind map image")

    mindmap_id = str(uuid.uuid4())
    minio_path = f"{session_id}/{mindmap_id}_mindmap.png"
    minio_client.upload_data(minio_path, image_bytes)
    minio_client.upload_data(LATEST_MINDMAP.format(session_id=session_id), image_bytes)
    try:
        create_mindmap(
            MindMap(id=mindmap_id, session_id=session_id, name=f"mindmap_{session_id}", source_path=minio_path)
        )
    except Exception as e:  # the image is still served through /get-mindmap
        logger.warning(f"[MindMap] row not saved for {session_id}: {e!r}")

    response_msg = generate_agent.invoke(
        {"messages": [HumanMessage(content=Prompts.MIND_MAP_COMPLETION_PROMPT)]},
        config=config,
    )
    content = response_msg["messages"][-1].content

    return {
        "messages": [AIMessage(content=content, name="mind_map")],
    }


def build_pdf_summarize_workflow():
    workflow = StateGraph(QState)
    workflow.add_node("summarize", summarize_node)
    workflow.add_node("extractive", extractive_node)
    workflow.add_node("merge", merge_node)
    workflow.add_node("mind_map", mind_map)

    workflow.add_edge(START, "summarize")
    workflow.add_edge("summarize", "extractive")
    workflow.add_edge("extractive", "merge")
    workflow.add_edge("merge", "mind_map")
    workflow.add_edge("mind_map", END)

    return workflow


work_flow = build_pdf_summarize_workflow()
pdf_summarize_agent = work_flow.compile()

if __name__ == "__main__":

    def print_stream(stream):
        for s in stream:
            message = s.get("messages", None)
            if message is None:
                logger.info(
                    " ".join(
                        str(_log_value)
                        for _log_value in (
                            "⚠️ Missing 'messages' key in stream item:",
                            s,
                        )
                    )
                )
                continue

            if isinstance(message, tuple):
                logger.info(" ".join(str(_log_value) for _log_value in ("Tuple message:", message)))
            elif isinstance(message, list):
                for m in message:
                    try:
                        m.pretty_print()
                    except AttributeError:
                        logger.info(m)
            else:
                try:
                    message.pretty_print()
                except AttributeError:
                    logger.info(message)

    input_path = str(DATA_DIR / "pdfs" / "example.pdf")

    inputs = {"file_path": input_path, "chunk_size": 10}

    print_stream(
        pdf_summarize_agent.stream(inputs, stream_mode="values", config={"callbacks": [tracer]})
    )
