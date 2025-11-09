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
SUMMARIZE_CHUNK_SUMMARY_PROMPT = """
Bên dưới là một tài liệu:
{document}

Hãy viết một bản tóm tắt bao gồm toàn bộ các thông tin chính.
Trong phần tóm tắt, không được nhắc đến các từ như “tài liệu” hoặc “bản tóm tắt”.
"""


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
            "text": SUMMARIZE_CHUNK_SUMMARY_PROMPT.format(
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
EXTRACTIVE_SUMMARIZE_PROMPT = """
Bạn là một mô hình tóm tắt trích chọn (extractive summarizer) có khả năng đánh giá mức độ quan trọng của từng câu dựa trên ngữ cảnh và ý nghĩa thông tin.

Bên dưới là một phần của tài liệu:
{document}

Hãy thực hiện các bước sau:

1. **Chấm điểm quan trọng** cho từng câu trong tài liệu dựa trên:
   - Mức độ chứa đựng thông tin trung tâm, kết luận hoặc phát hiện chính.
   - Sự liên kết với chủ đề tổng thể của tài liệu.
   - Mức độ độc lập và tự chứa (câu có thể hiểu mà không cần tham chiếu ra ngoài).

2. **Chọn ra các câu nổi bật nhất** (khoảng 5–10 câu hoặc ít hơn nếu văn bản ngắn),
   ưu tiên các câu có điểm quan trọng cao nhất, thể hiện được toàn bộ nội dung cốt lõi.

3. **Giữ nguyên nội dung gốc của các câu** (không viết lại, không diễn giải, không tóm gọn).

4. **Chỉ xuất ra danh sách các câu được chọn**, mỗi câu trên một dòng, theo đúng thứ tự xuất hiện trong tài liệu gốc.

Đầu ra cuối cùng là tập hợp các câu quan trọng nhất của tài liệu.
"""


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
            "text": EXTRACTIVE_SUMMARIZE_PROMPT.format(
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


# bước 3 : merge các bản tóm tắt của tài liệu với nhau dựa vào 2 bước trên để để tạo final summarize

Extract_Retrieve_Support_PROMPT = """
Bên dưới là nhiều bản tóm tắt của các phần khác nhau trong một tài liệu:
{document}
\n 
Bên dưới là các ngữ cảnh hỗ trợ tương ứng với những bản tóm tắt đã cho ở trên:
{context}

Hãy gộp các bản tóm tắt đã cho thành một bản tóm tắt duy nhất bao gồm toàn bộ các thông tin chính,
và sử dụng các ngữ cảnh hỗ trợ để đảm bảo rằng bản tóm tắt gộp không chứa sai lệch về mặt nội dung.
Phần nội dung chính của bản tóm tắt phải dựa hoàn toàn trên các bản tóm tắt đã cho,
trong khi các ngữ cảnh hỗ trợ chỉ được dùng để kiểm chứng tính chính xác.
Trong phần tóm tắt, không được nhắc đến các từ như “tài liệu”, “ngữ cảnh” hoặc “bản tóm tắt”.
    """

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
    prompt = Extract_Retrieve_Support_PROMPT.format(document=document, context=context)

    from langchain_core.messages import HumanMessage

    response_msg = generate_agent.invoke(
        {"messages": [HumanMessage(content=prompt)]}, config=config
    )
    content = response_msg["messages"][-1].content

    return {
        "messages": [AIMessage(content=content, name="final_summary")],
        "merge": content,
    }


# Xây dựng workflow


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
