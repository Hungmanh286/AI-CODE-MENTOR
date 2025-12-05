"""
Vector Store với xử lý song song để tăng tốc độ parsing PDF dài (300+ trang).

Các cải tiến so với vector_store.py:
1. ThreadPoolExecutor: Xử lý song song các chunks
2. Rate Limiting: Tránh vượt giới hạn API (RPM)
3. Progress Tracking: Theo dõi tiến trình thời gian thực
4. Error Handling: Xử lý lỗi chunk riêng lẻ không ảnh hưởng toàn bộ
"""

import os
from openai import OpenAI
from io import BytesIO
import base64
from google import genai
from google.genai import types
import datetime
import concurrent.futures
import time
from typing import List, Tuple
from dataclasses import dataclass

from pdf2image import convert_from_path
from langchain_docling import DoclingLoader
from langchain_docling.loader import ExportType
from langchain_voyageai.embeddings import VoyageAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from langchain_text_splitters import MarkdownHeaderTextSplitter
from tqdm import tqdm

from app.graph.prompts import Prompts
from app.config import settings

# Import rate_limit nếu có rateguard, hoặc tự implement
try:
    from rateguard import rate_limit

    HAS_RATEGUARD = True
except ImportError:
    HAS_RATEGUARD = False
    print("Warning: rateguard not installed. Install with: pip install rateguard")


# Configuration
@dataclass(frozen=True)
class ParallelConfig:
    MAX_WORKERS: int = 50
    RPM_LIMIT: int = 500
    CHUNK_SIZE_SMALL: int = 15
    CHUNK_SIZE_LARGE: int = 30
    RETRY_ATTEMPTS: int = 3
    RETRY_DELAY: int = 2


# Initialize clients
embeddings = VoyageAIEmbeddings(
    api_key=settings.EMBEDDING_KEY,
    model=settings.EMBEDDING_MODEL,
    output_dimension=settings.EMBEDDING_DIMS,
)
model = settings.CHAT_MODEL_VISION
api_key = settings.CHAT_MODEL_VISION_KEY
openai_client = OpenAI(api_key=api_key)
gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)

url = "http://localhost:6333"
prompt = Prompts.MARK_DOWN_PROMPT


if not HAS_RATEGUARD:
    # Simple rate limiter implementation nếu không có rateguard
    class SimpleRateLimiter:
        def __init__(self, rpm: int):
            self.rpm = rpm
            self.interval = 60.0 / rpm  # Seconds between calls
            self.last_call = 0

        def __call__(self, func):
            def wrapper(*args, **kwargs):
                now = time.time()
                time_since_last = now - self.last_call
                if time_since_last < self.interval:
                    time.sleep(self.interval - time_since_last)
                self.last_call = time.time()
                return func(*args, **kwargs)

            return wrapper

    rate_limit = lambda rpm: SimpleRateLimiter(rpm)


# ========== Parsing Functions with Rate Limiting ==========


@rate_limit(rpm=ParallelConfig.RPM_LIMIT)
def parse_chunk_openai(chunk_images: List[str]) -> str:
    """
    Parse chunk sử dụng OpenAI API với rate limiting.

    Args:
        chunk_images: Danh sách các ảnh base64

    Returns:
        Văn bản markdown từ chunk
    """
    content = [{"type": "input_text", "text": prompt}]

    for img_b64 in chunk_images:
        content.append(
            {
                "type": "input_image",
                "image_url": f"data:image/png;base64,{img_b64}",
            }
        )

    response = openai_client.responses.create(
        model=model, input=[{"role": "user", "content": content}]
    )

    return response.output_text or ""


@rate_limit(rpm=ParallelConfig.RPM_LIMIT)
def parse_chunk_gemini(chunk_images: List[str]) -> str:
    """
    Parse chunk sử dụng Gemini API với rate limiting.

    Args:
        chunk_images: Danh sách các ảnh base64

    Returns:
        Văn bản markdown từ chunk
    """
    # Tạo client mới cho mỗi thread để tránh thread-safety issues
    thread_gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)

    prompt_text = prompt
    contents = [prompt_text]

    for img_b64 in chunk_images:
        img_bytes = base64.b64decode(img_b64)
        contents.append(
            types.Part.from_bytes(
                data=img_bytes,
                mime_type="image/png",
            )
        )

    response = thread_gemini_client.models.generate_content(
        model="gemini-2.5-pro", contents=contents
    )

    return response.text or ""


def process_single_chunk(
    chunk_data: Tuple[int, List[str]], use_gemini: bool = True
) -> Tuple[int, str]:
    """
    Xử lý một chunk với retry logic.

    Args:
        chunk_data: Tuple (chunk_index, chunk_images)
        use_gemini: True để dùng Gemini, False để dùng OpenAI

    Returns:
        Tuple (chunk_index, parsed_text)
    """
    chunk_index, chunk_images = chunk_data

    for attempt in range(ParallelConfig.RETRY_ATTEMPTS):
        try:
            if use_gemini:
                result = parse_chunk_gemini(chunk_images)
            else:
                result = parse_chunk_openai(chunk_images)

            return (chunk_index, result)

        except Exception as e:
            if attempt < ParallelConfig.RETRY_ATTEMPTS - 1:
                print(
                    f"⚠️  Chunk {chunk_index} failed (attempt {attempt + 1}/{ParallelConfig.RETRY_ATTEMPTS}): {str(e)}"
                )
                time.sleep(ParallelConfig.RETRY_DELAY)
            else:
                print(
                    f"❌ Chunk {chunk_index} failed after {ParallelConfig.RETRY_ATTEMPTS} attempts: {str(e)}"
                )
                return (chunk_index, f"[ERROR: Failed to parse chunk {chunk_index}]")


def parse_pdf_parallel(
    file_path: str,
    use_gemini: bool = False,
    max_workers: int = ParallelConfig.MAX_WORKERS,
) -> str:
    """
    Parse PDF với xử lý song song các chunks.

    Args:
        file_path: Đường dẫn tới file PDF
        use_gemini: True để dùng Gemini API, False để dùng OpenAI
        max_workers: Số lượng worker threads

    Returns:
        Chuỗi markdown chứa nội dung toàn bộ PDF
    """
    print(f"🚀 Starting parallel PDF parsing: {file_path}")
    start_time = datetime.datetime.now()

    print("📄 Converting PDF to images...")
    images = convert_from_path(file_path)
    image_b64_list = []

    for img in images:
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode()
        image_b64_list.append(img_b64)

    total_pages = len(image_b64_list)
    print(f"📊 Total pages: {total_pages}")

    # Determine chunk size
    chunk_size = 8
    print(f"📦 Chunk size: {chunk_size} pages/chunk")

    # Split into chunks
    chunks_data = []
    start = 0
    chunk_index = 0

    while start < total_pages:
        end = min(start + chunk_size, total_pages)
        chunk = image_b64_list[start:end]
        chunks_data.append((chunk_index, chunk))
        start += chunk_size
        chunk_index += 1

    total_chunks = len(chunks_data)
    print(f"🔢 Total chunks: {total_chunks}")

    # Optimize worker count: use minimum of total_chunks and max_workers
    optimal_workers = min(total_chunks, max_workers)
    print(
        f"👷 Using {optimal_workers} worker threads (optimized from max {max_workers})"
    )
    print(f"⏱️  Rate limit: {ParallelConfig.RPM_LIMIT} requests/minute")
    print(f"🤖 Using {'Gemini' if use_gemini else 'OpenAI'} API\n")

    results = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=optimal_workers) as executor:
        # Submit all tasks
        futures = {
            executor.submit(process_single_chunk, chunk_data, use_gemini): chunk_data[0]
            for chunk_data in chunks_data
        }

        # Process results as they complete with progress bar
        with tqdm(total=total_chunks, desc="Processing chunks", unit="chunk") as pbar:
            for future in concurrent.futures.as_completed(futures):
                chunk_idx, chunk_text = future.result()
                results[chunk_idx] = chunk_text
                pbar.update(1)

    # Reconstruct document in correct order, filter out None values
    document_parts = [results[i] for i in sorted(results.keys()) if results[i]]

    document_str = "\n\n".join(document_parts)

    # Calculate statistics
    end_time = datetime.datetime.now()
    duration = end_time - start_time

    print("\nParsing complete!")
    print(f"Total time: {duration.total_seconds():.2f} seconds")
    print(
        f"Average time per chunk: {duration.total_seconds() / total_chunks:.2f} seconds"
    )
    print(f"Total characters: {len(document_str):,}")

    return document_str


# ========== Legacy Functions (compatibility) ==========


def parse_pdf_text(file_path: str):
    """Compatibility với code cũ - sử dụng Docling loader"""
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
    """Embedding documents vào Qdrant vector store"""
    collection_name = session_id

    client = QdrantClient(url="http://localhost:6333")
    existing_collections = [c.name for c in client.get_collections().collections]

    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[
            ("#", "Header_1"),
            ("##", "Header_2"),
            ("###", "Header_3"),
            ("####", "Header_4"),
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
