"""Vector store helpers with batched Gemini PDF parsing."""

import base64
import datetime
import os
import time
from io import BytesIO
from typing import List, Tuple

import structlog
from langchain_core.runnables import RunnableLambda
from langchain_qdrant import QdrantVectorStore
from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain_voyageai.embeddings import VoyageAIEmbeddings
from openai import OpenAI
from pdf2image import convert_from_path
from qdrant_client import QdrantClient
from tqdm import tqdm

from app.core.config import settings
from app.infra.prompts import Prompts

logger = structlog.get_logger(__name__)

try:
    from rateguard import rate_limit
except ImportError:
    logger.info("Warning: rateguard not installed. Install with: pip install rateguard")

    class SimpleRateLimiter:
        def __init__(self, rpm: int):
            self.interval = 60.0 / rpm
            self.last_call = 0.0

        def __call__(self, func):
            def wrapper(*args, **kwargs):
                now = time.time()
                elapsed = now - self.last_call
                if elapsed < self.interval:
                    time.sleep(self.interval - elapsed)
                self.last_call = time.time()
                return func(*args, **kwargs)

            return wrapper

    def rate_limit(rpm):
        return SimpleRateLimiter(rpm)


embeddings = VoyageAIEmbeddings(
    api_key=settings.EMBEDDING_KEY,
    model=settings.EMBEDDING_MODEL,
    output_dimension=settings.EMBEDDING_DIMS,
)

openrouter_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=settings.OPENROUTER_API_KEY,
)

url = settings._qdrant_url
prompt = Prompts.MARK_DOWN_PROMPT


@rate_limit(rpm=settings.PDF_PARSE_RPM_LIMIT)
def parse_chunk_gemini(chunk_images: List[str]) -> str:
    """Parse one image chunk with Gemini through OpenRouter."""
    content = [{"type": "text", "text": prompt}]

    for img_b64 in chunk_images:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{img_b64}"},
            }
        )

    response = openrouter_client.chat.completions.create(
        model=settings.MIND_MAP_MODEL,
        messages=[{"role": "user", "content": content}],
    )

    return response.choices[0].message.content or ""


def process_single_chunk(chunk_data: Tuple[int, List[str]]) -> Tuple[int, str]:
    """Parse one chunk with retry logic."""
    chunk_index, chunk_images = chunk_data

    for attempt in range(settings.PDF_PARSE_RETRY_ATTEMPTS):
        try:
            return (chunk_index, parse_chunk_gemini(chunk_images))
        except Exception as e:
            is_last_attempt = attempt == settings.PDF_PARSE_RETRY_ATTEMPTS - 1
            if is_last_attempt:
                logger.info(f"Chunk {chunk_index} failed: {e}")
                return (chunk_index, f"[ERROR: Failed to parse chunk {chunk_index}]")
            time.sleep(settings.PDF_PARSE_RETRY_DELAY)


def create_chunk_processor(pbar: tqdm) -> RunnableLambda:
    """Tạo runnable processor dùng cho batch xử lý danh sách chunks."""

    def run_chunk(chunk_data: Tuple[int, List[str]]) -> Tuple[int, str]:
        try:
            return process_single_chunk(chunk_data)
        finally:
            pbar.update(1)

    return RunnableLambda(run_chunk)


def encode_pdf_pages(file_path: str) -> List[str]:
    images = convert_from_path(file_path)
    encoded_pages = []

    for image in images:
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        encoded_pages.append(base64.b64encode(buffered.getvalue()).decode())

    return encoded_pages


def build_chunks(pages: List[str]) -> List[Tuple[int, List[str]]]:
    chunk_size = (
        settings.PDF_PARSE_CHUNK_SIZE_SMALL
        if len(pages) < settings.PDF_PARSE_CHUNK_SIZE_THRESHOLD
        else settings.PDF_PARSE_CHUNK_SIZE_LARGE
    )
    return [
        (index, pages[start : start + chunk_size])
        for index, start in enumerate(range(0, len(pages), chunk_size))
    ]


def parse_pdf_parallel(
    file_path: str,
    max_workers: int | None = None,
) -> str:
    """Parse PDF pages in batches with Gemini and return markdown."""
    start_time = datetime.datetime.now()

    pages = encode_pdf_pages(file_path)
    chunks_data = build_chunks(pages)
    total_chunks = len(chunks_data)
    if total_chunks == 0:
        return ""

    worker_limit = max_workers or settings.PDF_PARSE_MAX_WORKERS
    max_concurrency = min(total_chunks, worker_limit)
    logger.info(
        f"Parsing PDF with Gemini: {len(pages)} pages, {total_chunks} chunks, {max_concurrency} workers"
    )

    with tqdm(total=total_chunks, desc="Processing chunks", unit="chunk") as pbar:
        chunk_processor = create_chunk_processor(pbar=pbar)
        parallel_results = chunk_processor.batch(
            chunks_data,
            config={"max_concurrency": max_concurrency},
        )

    results = {}
    for chunk_idx, chunk_text in parallel_results:
        results[chunk_idx] = chunk_text

    document_parts = [results[i] for i in sorted(results.keys()) if results[i]]
    document_str = "\n\n".join(document_parts)

    logger.info(
        f"PDF parsing completed in {(datetime.datetime.now() - start_time).total_seconds():.2f}s"
    )
    return document_str


def parse_pdf_text(file_path: str):
    """Compatibility với code cũ - sử dụng Docling loader"""
    try:
        if not os.path.exists(file_path):
            return None
        from langchain_docling import DoclingLoader
        from langchain_docling.loader import ExportType

        loader = DoclingLoader(
            file_path=file_path,
            export_type=ExportType.MARKDOWN,
        )
        docs = loader.load()
        return docs
    except Exception as e:
        logger.info(f"Error parsing PDF text: {e}")
        return None


def embedding_document(docs, session_id: str):
    """Embedding documents vào Qdrant vector store"""
    collection_name = session_id

    client = QdrantClient(url=settings._qdrant_url)
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

        logger.info(
            " ".join(
                str(_log_value)
                for _log_value in ("Error in embedding_document:", str(e))
            )
        )
        logger.info(traceback.format_exc())
