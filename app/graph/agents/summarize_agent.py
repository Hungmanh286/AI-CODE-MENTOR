import structlog

import uuid

from langgraph.graph import StateGraph, START, END
from langchain_core.runnables import RunnableConfig
from langfuse.langchain import CallbackHandler
from langgraph.graph.message import MessagesState
from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain_core.messages import AIMessage, HumanMessage


from app.config import settings
from app.graph.prompts import Prompts
from app.services.datasource import get_active_file_id
from app.services.minio_client import minio_client
from app.graph.generate import generate_agent
from app.chatmodel import init_llm
from app.routes.mindmap import create_mindmap
from app.schema.mindmap import MindMap


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
            chunk_text = "\n".join(
                [split.page_content for split in splits[i : i + chunk_size]]
            )
            extractive_chunk = Prompts.EXTRACTIVE_SUMMARIZE_PROMPT.format(
                chunk_text=chunk_text
            )

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
    context = "\n".join(
        [f"Chunk {i}:\n" + e for i, e in enumerate(extractive_summaries)]
    )
    prompt = Prompts.Extract_Retrieve_Support_PROMPT.format(
        document=document, context=context
    )

    response_msg = llm.invoke(input=prompt, config=config)

    content = response_msg.content

    return {
        "merge": content,
    }


def mind_map(state: QState, config: RunnableConfig):
    merge = state.get("merge", "")
    session_id = config["configurable"].get("thread_id")

    from openai import OpenAI

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.OPENROUTER_API_KEY,
    )

    prompt = Prompts.MIND_MAP_PROMPT.format(merge=merge)

    response = client.chat.completions.create(
        model=settings.MIND_MAP_MODEL, messages=[{"role": "user", "content": prompt}]
    )

    content = response.choices[0].message.content
    logger.info(f"[MindMap] Generated content: {content[:100]}...")

    # Image generation is not directly supported via OpenRouter's standard chat API
    # for models like gemini-2.5-flash-image-preview in the same way as native SDK.
    # We return the text content which can be used to render a mindmap.

    for part in response.parts:
        if part.text is not None:
            content = part.text
        if part.inline_data is not None:
            image = part.as_image()

            temp_image_path = f"temp_mindmap_{session_id}.png"
            image.save(temp_image_path)

            mindmap_id = str(uuid.uuid4())
            minio_path = f"{session_id}/{mindmap_id}_mindmap.png"

            with open(temp_image_path, "rb") as f:
                image_bytes = f.read()
                minio_client.upload_data(minio_path, image_bytes)

            import os

            try:
                mindmap_data = MindMap(
                    id=mindmap_id,
                    session_id=session_id,
                    name=f"mindmap_{session_id}",
                    source_path=minio_path,
                )
                create_mindmap(mindmap=mindmap_data)
            except Exception as e:
                logger.info(e)
            os.remove(temp_image_path)

    prompt2 = """
    Chỉ cần trả lời là tôi đã tạo xong mind map
    """

    response_msg = generate_agent.invoke(
        {"messages": [HumanMessage(content=prompt2)]}, config=config
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
                logger.info(
                    " ".join(
                        str(_log_value) for _log_value in ("Tuple message:", message)
                    )
                )
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

    input_path = "/home/hungmanh/Documents/CodeMentor/app/data/example.pdf"

    inputs = {"file_path": input_path, "chunk_size": 10}

    print_stream(
        pdf_summarize_agent.stream(
            inputs, stream_mode="values", config={"callbacks": [tracer]}
        )
    )
