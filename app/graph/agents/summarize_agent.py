import os
from openai import OpenAI

from langgraph.graph import StateGraph, START, END
from langchain_core.runnables import RunnableConfig
from langfuse.callback import CallbackHandler
from langgraph.graph.message import MessagesState
from langchain_core.messages import (
    AIMessage,
)
from langchain_text_splitters import MarkdownHeaderTextSplitter

from app.config import settings
from app.graph.generate import generate_agent
from app.graph.prompts import Prompts
from app.services.datasource import get_active_file_id
from app.services.minio_client import minio_client


class QState(MessagesState):
    file_path: str | None
    chunk_size: int | None
    extractive_summaries: list[dict] | None
    summaries: list[dict] | None
    merge: str | None


model = settings.CHAT_MODEL_VISION
api_key = settings.CHAT_MODEL_VISION_KEY
client = OpenAI(api_key=api_key)


tracer = CallbackHandler(
    tags=["code"],
    public_key=settings.LANGFUSE_PUBLIC_KEY,
    secret_key=settings.LANGFUSE_SECRET_KEY,
    host=settings.LANGFUSE_HOST,
)


# Tóm tắt văn bản :
# Node 1: Tóm tắt từng chunk
def summarize_node(state: QState, config: RunnableConfig):
    summarize_chunks = []

    session_id = config["configurable"].get("thread_id")
    file_ids = get_active_file_id(session_id)

    chunk_size = 10
    for file_id in file_ids:
        # Đọc docs từ MinIO (trong folder session)
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

                # Gộp các split lại thành các chunk với chunk_size
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
        # Đọc docs từ MinIO (trong folder session)
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

        # Gộp các split lại thành các chunk với chunk_size
        for i in range(0, total_splits, chunk_size):
            chunk_text = "\n".join(
                [split.page_content for split in splits[i : i + chunk_size]]
            )
            extractive_chunk = Prompts.EXTRACTIVE_SUMMARIZE_PROMPT.format(
                chunk_text=chunk_text
            )

            extractive_summaries.append(extractive_chunk)

    return {"extractive_summaries": extractive_summaries}

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

    from langchain_core.messages import HumanMessage

    response_msg = generate_agent.invoke(
        {"messages": [HumanMessage(content=prompt)]}, config=config
    )
    content = response_msg["messages"][-1].content

    return {
        "messages": [AIMessage(content=content, name="final_summary")],
        "merge": content,
    }

# def mind_map(state: QState, config: RunnableConfig):
#     merge = state.get("merge", "")

#     response = client.responses.create(
#         model="gpt-5-mini",
#         input="Tạo mind map từ nội dung sau:{merge}",
#         tools=[{"type": "image_generation"}],
#     )

#     # Save the image to a file
#     image_data = [
#         output.result
#         for output in response.output
#         if output.type == "image_generation_call"
#     ]

#     if image_data:
#         image_base64 = image_data[0]
#         with open("/home/hungmanh/Documents/CodeMentor/app/data/otter.png", "wb") as f:
#             f.write(base64.b64decode(image_base64))


def build_pdf_summarize_workflow():
    workflow = StateGraph(QState)
    workflow.add_node("summarize", summarize_node)
    workflow.add_node("extractive", extractive_node)
    workflow.add_node("merge", merge_node)
    workflow.add_edge(START, "summarize")
    workflow.add_edge("summarize", "extractive")
    workflow.add_edge("extractive", "merge")
    workflow.add_edge("merge", END)

    return workflow


work_flow = build_pdf_summarize_workflow()
pdf_summarize_agent = work_flow.compile()

if __name__ == "__main__":

    def print_stream(stream):
        for s in stream:
            message = s.get("messages", None)
            if message is None:
                print("⚠️ Missing 'messages' key in stream item:", s)
                continue

            if isinstance(message, tuple):
                print("Tuple message:", message)
            elif isinstance(message, list):
                for m in message:
                    try:
                        m.pretty_print()
                    except AttributeError:
                        print(m)
            else:
                try:
                    message.pretty_print()
                except AttributeError:
                    print(message)

    input_path = "/home/hungmanh/Documents/CodeMentor/app/data/example.pdf"

    inputs = {"file_path": input_path, "chunk_size": 10}

    print_stream(
        pdf_summarize_agent.stream(
            inputs, stream_mode="values", config={"callbacks": [tracer]}
        )
    )
