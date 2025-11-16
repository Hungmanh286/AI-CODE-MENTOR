import os
from openai import OpenAI
from io import BytesIO
import base64

from pdf2image import convert_from_path
from langchain_docling import DoclingLoader
from langchain_docling.loader import ExportType
from langchain_voyageai.embeddings import VoyageAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from langchain_text_splitters import MarkdownHeaderTextSplitter

from app.config import settings

embeddings = VoyageAIEmbeddings(
    api_key=settings.EMBEDDING_KEY,
    model=settings.EMBEDDING_MODEL,
    output_dimension=settings.EMBEDDING_DIMS,
)

model = settings.CHAT_MODEL_VISION
api_key = settings.CHAT_MODEL_VISION_KEY
client = OpenAI(api_key=api_key)


url = "http://localhost:6333"


def parse_pdf_text(file_path: str):
    try:
        if not os.path.exists(file_path):
            return None
        loader = DoclingLoader(
            file_path=file_path,
            export_type=ExportType.MARKDOWN,
        )
        docs = loader.load()
        return docs
    except Exception as e:
        print(f"Error parsing PDF text: {e}")
        return None


def embedding_document(docs, session_id: str):
    collection_name = session_id

    client = QdrantClient(url="http://localhost:6333")

    existing_collections = [c.name for c in client.get_collections().collections]

    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[
            ("#", "Header_1"),
            ("##", "Header_2"),
            ("###", "Header_3"),
        ],
    )
    splits = [split for doc in docs for split in splitter.split_text(doc)]

    try:
        if collection_name not in existing_collections:
            vector_store = QdrantVectorStore.from_documents(
                splits,
                embeddings,
                url=url,
                prefer_grpc=True,
                collection_name=collection_name,
            )
        else:
            vector_store = QdrantVectorStore(
                client=client,
                collection_name=collection_name,
                embedding=embeddings,
            )
            vector_store.add_documents(splits)
    except Exception as e:
        import traceback

        print("Error in embedding_document:", str(e))
        print(traceback.format_exc())
        print("splits type:", type(splits))
        if splits:
            print("First split type:", type(splits[0]))
            print("First split content:", getattr(splits[0], "page_content", splits[0]))


def parse_chunk(chunk_images: list) -> str:
    """
    Parse nội dung từ 1 chunk (nhóm các trang) từ PDF.

    Args:
        chunk_images: Danh sách các ảnh base64 trong chunk
        chunk_index: Chỉ số của chunk

    Returns:
        Bản tóm tắt của chunk
    """
    content = [
        {
            "type": "input_text",
            "text": "Chuyển ảnh sang văn bản Markdown. Giữ nguyên cấu trúc, các tiêu đề phải dùng đúng dấu #, ##, ### theo cấp độ heading trong tài liệu gốc. Không bỏ sót bất kỳ phần nào, không tự ý thay đổi nội dung. Đầu ra là văn bản Markdown chuẩn, mỗi header phải bắt đầu bằng dấu # đúng cấp độ.",
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


def parse_pdf_text2(file_path: str):
    images = convert_from_path(file_path)
    image_b64_list = []
    for img in images:
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode()
        image_b64_list.append(img_b64)

    total_pages = len(image_b64_list)

    if total_pages < 50:
        chunk_size = 15
    elif 50 <= total_pages <= 150:
        chunk_size = 30
    else:
        chunk_size = 50

    chunks = []
    start = 0
    while start < total_pages:
        end = min(start + chunk_size, total_pages)
        chunk = image_b64_list[start:end]
        chunk_summary = parse_chunk(chunk)
        chunks.append(chunk_summary)
        start += chunk_size
    # Kết hợp các chunk thành một chuỗi duy nhất, phân tách bằng 2 dòng trống
    document_str = "\n\n".join(chunks)
    return document_str


if __name__ == "__main__":
    pdf_path = "/home/hungmanh/Documents/CodeMentor/app/data/example.pdf"
    doc = parse_pdf_text2(pdf_path)
    embedding_document([doc], "test_session")
