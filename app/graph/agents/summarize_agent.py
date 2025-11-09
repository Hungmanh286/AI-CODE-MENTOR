import base64
from openai import OpenAI
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from app.config import settings
from app.graph.state import State
from pdf2image import convert_from_path
from io import BytesIO

# Prompt cho các bước
SUMMARIZE_CHUNK_SUMMARY_PROMPT = """
Bên dưới là một tài liệu:
{document}
Hãy viết một bản tóm tắt bao gồm toàn bộ các thông tin chính.
Trong phần tóm tắt, không được nhắc đến các từ như “tài liệu” hoặc “bản tóm tắt”.
"""
EXTRACTIVE_SUMMARIZE_PROMPT = """
Bạn là một mô hình tóm tắt trích chọn (extractive summarizer) có khả năng đánh giá mức độ quan trọng của từng câu dựa trên ngữ cảnh và ý nghĩa thông tin.
Bên dưới là một phần của tài liệu:
{document}
Hãy thực hiện các bước sau:
1. Chấm điểm quan trọng cho từng câu trong tài liệu.
2. Chọn ra các câu nổi bật nhất, giữ nguyên nội dung gốc.
3. Chỉ xuất ra danh sách các câu được chọn, mỗi câu trên một dòng.
"""
Extract_Retrieve_Support_PROMPT = """
Bên dưới là nhiều bản tóm tắt của các phần khác nhau trong một tài liệu:
{document}
Bên dưới là các ngữ cảnh hỗ trợ tương ứng với những bản tóm tắt đã cho ở trên:
{context}
Hãy gộp các bản tóm tắt đã cho thành một bản tóm tắt duy nhất bao gồm toàn bộ các thông tin chính,
và sử dụng các ngữ cảnh hỗ trợ để đảm bảo rằng bản tóm tắt gộp không chứa sai lệch về mặt nội dung.
Phần nội dung chính của bản tóm tắt phải dựa hoàn toàn trên các bản tóm tắt đã cho,
trong khi các ngữ cảnh hỗ trợ chỉ được dùng để kiểm chứng tính chính xác.
Trong phần tóm tắt, không được nhắc đến các từ như “tài liệu”, “ngữ cảnh” hoặc “bản tóm tắt”.
"""

client = OpenAI(api_key=settings.CHAT_MODEL_VISION_KEY)
model = settings.CHAT_MODEL_VISION


# Node 1: Tóm tắt từng chunk
def summarize_pdf_by_chunks(file_path, chunk_size=3):
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
        content = [
            {
                "type": "input_text",
                "text": SUMMARIZE_CHUNK_SUMMARY_PROMPT.format(
                    document=f"Đây là phần {i // chunk_size + 1} của tài liệu (các trang được thể hiện dưới dạng hình ảnh)"
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
        summaries.append(
            {
                "chunk_index": i // chunk_size,
                "pages": f"{i + 1}-{min(i + chunk_size, total_pages)}",
                "summary": response.output_text,
            }
        )
    return summaries


# Node 2: Extractive Summarization từng chunk
def extractive_summarize_pdf_by_chunks(file_path, chunk_size=3):
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
        content = [
            {
                "type": "input_text",
                "text": EXTRACTIVE_SUMMARIZE_PROMPT.format(
                    document=f"Đây là phần {i // chunk_size + 1} của tài liệu (các trang được thể hiện dưới dạng hình ảnh)"
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
        summaries.append(
            {
                "chunk_index": i // chunk_size,
                "pages": f"{i + 1}-{min(i + chunk_size, total_pages)}",
                "summary": response.output_text,
            }
        )
    return summaries


# Node 3: Merge hai kết quả
def merge_node(state: State, config: RunnableConfig):
    summaries = state.summaries
    extractive_summaries = state.extractive_summaries
    document = "\n".join([s["summary"] for s in summaries])
    context = "\n".join([e["summary"] for e in extractive_summaries])
    prompt = Extract_Retrieve_Support_PROMPT.format(document=document, context=context)
    response = client.responses.create(
        model=model, input=[{"role": "user", "content": prompt}]
    )
    return {"merged": response.output_text}


# Node wrappers
def summarize_node(state: State, config: RunnableConfig):
    summaries = summarize_pdf_by_chunks(state.file_path, state.chunk_size)
    state.summaries = summaries
    return state


def extractive_node(state: State, config: RunnableConfig):
    extractive_summaries = extractive_summarize_pdf_by_chunks(
        state.file_path, state.chunk_size
    )
    state.extractive_summaries = extractive_summaries
    return state


# Build workflow
def build_summarize_workflow():
    workflow = StateGraph(State)
    workflow.add_node("summarize", summarize_node)
    workflow.add_node("extractive", extractive_node)
    workflow.add_node("merge", merge_node)
    workflow.add_edge(START, "summarize")
    workflow.add_edge("summarize", "extractive")
    workflow.add_edge("extractive", "merge")
    workflow.add_edge("merge", END)
    return workflow


workflow = build_summarize_workflow().compile()
summarize_agent = workflow

if __name__ == "__main__":
    from langchain_core.messages import HumanMessage

    def print_stream(stream):
        for s in stream:
            message = s["messages"][-1]
            if isinstance(message, tuple):
                print(message)
            else:
                message.pretty_print()

    inputs = {"messages": [HumanMessage(content="4 nhân 9 bao nhiêu")]}
    print_stream(summarize_agent.stream(inputs, stream_mode="values"))
