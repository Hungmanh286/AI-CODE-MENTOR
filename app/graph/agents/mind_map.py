from langgraph.graph import StateGraph, START, END
from langchain_core.runnables import RunnableConfig
from langfuse.callback import CallbackHandler
from langgraph.graph.message import MessagesState
import concurrent.futures
from tqdm import tqdm


from app.config import settings
from app.graph.prompts import Prompts
from app.chatmodel import init_llm
from app.services.datasource import get_active_file_id
from app.services.minio_client import minio_client


class QState(MessagesState):
    file_path: str | None
    query: str | None
    document_chunks: list[str] | None
    extractive_summaries: list[dict] | None
    summaries: list[dict] | None
    merge: str | None


tracer = CallbackHandler(
    tags=["code"],
    public_key=settings.LANGFUSE_PUBLIC_KEY,
    secret_key=settings.LANGFUSE_SECRET_KEY,
    host=settings.LANGFUSE_HOST,
)


# Node 0: Tiền xử lý tài liệu
def document_preprocessing(state: QState, config: RunnableConfig):
    """Tiền xử lý tài liệu: tách nhỏ văn bản thành các đoạn (chunks) với overlap."""
    session_id = config["configurable"].get("thread_id")
    file_ids = get_active_file_id(session_id)
    query = state.get("query", None)
    document_chunks = []

    for file_id in file_ids:
        docs_minio_path = f"{session_id}/{file_id}_docs.txt"

        if minio_client.file_exists(docs_minio_path):
            docs_data = minio_client.download_data(docs_minio_path)
            if docs_data:
                docs_content = docs_data.decode("utf-8")

                # Chia docs_content thành các phần có overlap
                content_length = len(docs_content)
                if content_length < 5000:
                    num_parts = 3
                    chunk_size = content_length // num_parts
                    overlap_size = chunk_size // 20

                elif 5000 <= content_length < 10000:
                    num_parts = 5
                    chunk_size = content_length // num_parts
                    overlap_size = chunk_size // 20

                elif 10000 <= content_length < 30000:
                    num_parts = 8
                    chunk_size = content_length // num_parts
                    overlap_size = chunk_size // 20
                else:
                    num_parts = 10
                    chunk_size = content_length // num_parts
                    overlap_size = chunk_size // 20

                print(f"File {file_id}: Total content length = {content_length} chars")
                print(
                    f"Splitting into {num_parts} parts with {overlap_size} chars overlap"
                )
                print(f"Each chunk: ~{chunk_size} chars")

                for part_idx in range(num_parts):
                    start_idx = max(
                        0, part_idx * chunk_size - overlap_size if part_idx > 0 else 0
                    )
                    end_idx = min((part_idx + 1) * chunk_size, content_length)

                    part_content = docs_content[start_idx:end_idx]
                    document_chunks.append(part_content)

                    print(
                        f"Part {part_idx + 1}/{num_parts}: {len(part_content)} chars (from {start_idx} to {end_idx})"
                    )

                print(f"\nCreated {len(document_chunks)} chunks with overlap")

    return {"document_chunks": document_chunks, "query": query}


# Node 1: Tóm tắt từng chunk (PARALLEL)
def summarize_node(state: QState, config: RunnableConfig):
    document_chunks = state.get("document_chunks", [])

    llm = init_llm(
        api_key=settings.CHAT_MODEL_KEY,
        model=settings.CHAT_MODEL,
        temperature=settings.CHAT_MODEL_TEMPERATURE_VISION,
        tags=["agent"],
    )

    def process_single_summary(chunk_data):
        """Process một chunk và tạo summary"""
        idx, chunk_text = chunk_data
        try:
            print(f"Processing summary for chunk {idx + 1}/{len(document_chunks)}")
            prompt = Prompts.SUMMARIZE_CHUNK_SUMMARY_PROMPT.format(document=chunk_text)
            response = llm.invoke(input=prompt, config=config)
            return (idx, response.content)
        except Exception as e:
            print(f"Error summarizing chunk {idx}: {e}")
            return (idx, f"[ERROR: Failed to summarize chunk {idx}]")

    max_workers = min(30, len(document_chunks))
    chunks_data = [(idx, chunk) for idx, chunk in enumerate(document_chunks)]

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_single_summary, chunk_data): chunk_data[0]
            for chunk_data in chunks_data
        }

        results = {}
        with tqdm(total=len(futures), desc="Summarizing chunks") as pbar:
            for future in concurrent.futures.as_completed(futures):
                idx, summary = future.result()
                results[idx] = summary
                pbar.update(1)

    # Sắp xếp theo index để đảm bảo thứ tự
    summaries = [results[idx] for idx in sorted(results.keys())]

    print(f"Generated {len(summaries)} summaries in parallel")
    return {"summaries": summaries}


# Node 2: Extractive Summarization từng chunk (PARALLEL)
def extractive_node(state: QState, config: RunnableConfig):
    document_chunks = state.get("document_chunks", [])

    llm = init_llm(
        api_key=settings.CHAT_MODEL_KEY,
        model=settings.CHAT_MODEL,
        temperature=settings.CHAT_MODEL_TEMPERATURE_VISION,
        tags=["agent"],
    )

    def process_single_extractive(chunk_data):
        """Process một chunk và tạo extractive summary"""
        idx, chunk_text = chunk_data
        try:
            print(
                f"Processing extractive summary for chunk {idx + 1}/{len(document_chunks)}"
            )
            prompt = Prompts.EXTRACTIVE_SUMMARIZE_PROMPT.format(chunk_text=chunk_text)
            response = llm.invoke(input=prompt, config=config)
            return (idx, response.content)
        except Exception as e:
            print(f"Error extractive summarizing chunk {idx}: {e}")
            return (idx, f"[ERROR: Failed to extractive summarize chunk {idx}]")

    max_workers = min(30, len(document_chunks))
    chunks_data = [(idx, chunk) for idx, chunk in enumerate(document_chunks)]

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_single_extractive, chunk_data): chunk_data[0]
            for chunk_data in chunks_data
        }

        results = {}
        with tqdm(total=len(futures), desc="Extractive summarizing chunks") as pbar:
            for future in concurrent.futures.as_completed(futures):
                idx, extractive_summary = future.result()
                results[idx] = extractive_summary
                pbar.update(1)

    # Sắp xếp theo index để đảm bảo thứ tự
    extractive_summaries = [results[idx] for idx in sorted(results.keys())]

    print(f"Generated {len(extractive_summaries)} extractive summaries in parallel")
    return {"extractive_summaries": extractive_summaries}


llm = init_llm(
    api_key=settings.CHAT_MODEL_KEY,
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

    return {"merge": content, "messages": content}


def build_pdf_summarize_workflow():
    workflow = StateGraph(QState)
    workflow.add_node("preprocessing", document_preprocessing)
    workflow.add_node("summarize", summarize_node)
    workflow.add_node("extractive", extractive_node)
    workflow.add_node("merge", merge_node)

    workflow.add_edge(START, "preprocessing")
    workflow.add_edge("preprocessing", "summarize")
    workflow.add_edge("summarize", "extractive")
    workflow.add_edge("extractive", "merge")
    workflow.add_edge("merge", END)

    return workflow


work_flow = build_pdf_summarize_workflow()
summarize_agent = work_flow.compile()
