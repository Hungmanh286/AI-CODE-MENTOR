from openai import OpenAI
import base64
from pdf2image import convert_from_path
from io import BytesIO

from langgraph.graph import StateGraph, START, END
from langchain_core.runnables import RunnableConfig
from langfuse.callback import CallbackHandler
from langgraph.graph.message import MessagesState
from langchain_core.messages import (
    AIMessage,
)

from app.config import settings
from app.graph.generate import generate_agent
from app.graph.prompts import Prompts


# sử dụng phương pháp merge bằng việc kết hợp giữa tóm tắt và tóm tắt trích xuất để tóm tắt
# long document
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

# bước 1 : tóm tắt từng tài liệu (document summarizztion) cho mỗi đoạn


def summarize_chunk(chunk_images: list, chunk_index: int) -> str:
    """
    Tóm tắt một chunk (nhóm các trang) từ PDF.

    Args:
        chunk_images: Danh sách các ảnh base64 trong chunk
        chunk_index: Chỉ số của chunk

    Returns:
        Bản tóm tắt của chunk
    """
    content = [
        {
            "type": "input_text",
            "text": Prompts.SUMMARIZE_CHUNK_SUMMARY_PROMPT.format(
                document=f"Đây là phần {chunk_index + 1} của tài liệu (các trang được thể hiện dưới dạng hình ảnh)"
            ),
        }
    ]

    for img_b64 in chunk_images:
        content.append(
            {
                "type": "input_image",
                "image_url": f"data:image/png;base64,{img_b64}",
            }
        )

    response = client.responses.create(
        model=model, input=[{"role": "user", "content": content}]
    )

    return response.output_text


def summarize_pdf_by_chunks(file_path: str, chunk_size: int = 3) -> list:
    """
    Tóm tắt PDF theo từng chunk.

    Args:
        file_path: Đường dẫn đến file PDF
        chunk_size: Số trang trong mỗi chunk

    Returns:
        Danh sách các bản tóm tắt của từng chunk
    """
    # Convert PDF thành ảnh
    images = convert_from_path(file_path, dpi=200)

    # Chuyển đổi ảnh sang base64
    image_b64_list = []
    for img in images:
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode()
        image_b64_list.append(img_b64)

    # Chia thành các chunks
    summaries = []
    total_pages = len(image_b64_list)

    for i in range(0, total_pages, chunk_size):
        chunk_images = image_b64_list[i : i + chunk_size]
        chunk_summary = summarize_chunk(chunk_images, i // chunk_size)
        summaries.append(
            {
                "chunk_index": i // chunk_size,
                "pages": f"{i + 1}-{min(i + chunk_size, total_pages)}",
                "summary": chunk_summary,
            }
        )
        print(
            f"Đã tóm tắt chunk {i // chunk_size + 1} (trang {i + 1}-{min(i + chunk_size, total_pages)})"
        )

    return summaries


# bước 2 : Extractive Summarization cho mỗi đoạn (chọn ra các câu nổi bật nhất từ tài liệu nguồn)


def extractive_summarize_chunk(chunk_images: list, chunk_index: int) -> str:
    """
    Trích xuất các câu nổi bật nhất từ một chunk (nhóm các trang) của PDF.

    Args:
        chunk_images: Danh sách các ảnh base64 trong chunk
        chunk_index: Chỉ số của chunk

    Returns:
        Các câu nổi bật nhất từ chunk
    """
    content = [
        {
            "type": "input_text",
            "text": Prompts.EXTRACTIVE_SUMMARIZE_PROMPT.format(
                document=f"Đây là phần {chunk_index + 1} của tài liệu (các trang được thể hiện dưới dạng hình ảnh)"
            ),
        }
    ]
    for img_b64 in chunk_images:
        content.append(
            {"type": "input_image", "image_url": f"data:image/png;base64,{img_b64}"}
        )
    response = client.responses.create(
        model=model, input=[{"role": "user", "content": content}]
    )
    return response.output_text


def extractive_summarize_pdf_by_chunks(file_path: str, chunk_size: int = 3) -> list:
    """
    Trích xuất các câu nổi bật nhất từ PDF theo từng chunk.

    Args:
        file_path: Đường dẫn đến file PDF
        chunk_size: Số trang trong mỗi chunk

    Returns:
        Danh sách các câu nổi bật nhất của từng chunk
    """
    images = convert_from_path(file_path, dpi=200)
    image_b64_list = []
    for img in images:
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode()
        image_b64_list.append(img_b64)

    summaries = []
    total_pages = len(image_b64_list)
    for i in range(0, total_pages, chunk_size):
        chunk_images = image_b64_list[i : i + chunk_size]
        chunk_summary = extractive_summarize_chunk(chunk_images, i // chunk_size)
        summaries.append(
            {
                "chunk_index": i // chunk_size,
                "pages": f"{i + 1}-{min(i + chunk_size, total_pages)}",
                "summary": chunk_summary,
            }
        )
        print(
            f"Đã extractive summarize chunk {i // chunk_size + 1} (trang {i + 1}-{min(i + chunk_size, total_pages)})"
        )
    return summaries


# Node 1: Tóm tắt từng chunk
def summarize_node(state: QState, config: RunnableConfig):
    file_path = state["file_path"]
    chunk_size = state.get("chunk_size", 3)
    summaries = summarize_pdf_by_chunks(file_path, chunk_size)

    return {"summaries": summaries}


# Node 2: Extractive Summarization từng chunk
def extractive_node(state: QState, config: RunnableConfig):
    file_path = state["file_path"]
    chunk_size = state.get("chunk_size", 3)
    extractive_summaries = extractive_summarize_pdf_by_chunks(file_path, chunk_size)

    return {"extractive_summaries": extractive_summaries}


# Node 3: Merge hai kết quả
def merge_node(state: QState, config: RunnableConfig):
    summaries = state["summaries"]
    extractive_summaries = state["extractive_summaries"]
    # Chuẩn bị dữ liệu cho prompt
    document = "\n".join([s["summary"] for s in summaries])
    context = "\n".join([e["summary"] for e in extractive_summaries])
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
            # Kiểm tra xem phần tử có khóa "messages" hay không
            message = s.get("messages", None)
            if message is None:
                print("⚠️ Missing 'messages' key in stream item:", s)
                continue

            # Nếu message là tuple (thường từ LangGraph astream_events)
            if isinstance(message, tuple):
                print("Tuple message:", message)
            # Nếu là danh sách các message
            elif isinstance(message, list):
                for m in message:
                    try:
                        m.pretty_print()
                    except AttributeError:
                        print(m)
            # Nếu là object Message duy nhất
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
