"""Documents of a chat session for the AG-UI agent: which files, which passages.

Storage written by the existing upload flow (``/upload``, ``/update-file-active``):
* ``upload_file_status`` rows: ``file_id``, ``file_name``, ``active``, ``has_processed``
* MinIO ``{session_id}/{file_id}_docs.txt``: the parsed markdown of one file
* Qdrant collection ``{session_id}``: markdown sections of every processed file.
  Chunks embedded since the AG-UI port carry ``file_id``/``file_name`` metadata;
  older chunks do not, so they can only be attributed when the session has a
  single processed file (``attribute_hits``).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, TypedDict

import structlog
from sqlmodel import Session, select

from app.core.config import settings
from app.db.models.upload import UploadFileStatus

logger = structlog.get_logger(__name__)

# Upper bound of one document's text handed to the LLM for whole-document tasks
# (summary, quiz, mind map); gpt-4.1-mini's window is far larger, cost is not.
MAX_DOCUMENT_CHARS = 60_000


class RetrievedChunk(TypedDict):
    file_id: str
    file_name: str
    page: int | None
    text: str


@dataclass(frozen=True)
class DocRef:
    file_id: str
    file_name: str
    active: bool
    has_processed: bool


def session_documents(session_id: str) -> list[DocRef]:
    with Session(settings._app_db_engine) as db:
        rows = db.exec(select(UploadFileStatus).where(UploadFileStatus.session_id == session_id)).all()
    return [
        DocRef(
            file_id=str(r.file_id),
            file_name=r.file_name,
            active=bool(r.active),
            has_processed=bool(r.has_processed),
        )
        for r in rows
        if r.file_id
    ]


def select_documents(files: Sequence[DocRef], client_ids: Sequence[str]) -> list[DocRef]:
    """Documents the run should use.

    The frontend does not send ``active_document_ids`` yet (contract 4.4: ``[]``),
    so an empty list means "the files switched on in the source panel"
    (``active``). Ids sent by the client are only honoured for files of this
    session.
    """
    if client_ids:
        wanted = set(client_ids)
        return [f for f in files if f.file_id in wanted]
    return [f for f in files if f.active]


def attribute_hits(
    hits: Sequence[tuple[str, Mapping[str, Any]]],
    selected: Sequence[DocRef],
    session_files: Sequence[DocRef],
) -> list[RetrievedChunk]:
    """Keep the hits that belong to a selected document, with their file."""
    by_id = {d.file_id: d for d in selected}
    processed = [f for f in session_files if f.has_processed]
    legacy_owner = by_id.get(processed[0].file_id) if len(processed) == 1 else None
    chunks: list[RetrievedChunk] = []
    for text, metadata in hits:
        file_id = metadata.get("file_id")
        doc = by_id.get(str(file_id)) if file_id else legacy_owner
        if doc is None or not text.strip():
            continue
        chunks.append(
            {"file_id": doc.file_id, "file_name": doc.file_name, "page": None, "text": text.strip()}
        )
    return chunks


def search_session(session_id: str, question: str, k: int) -> list[tuple[str, dict]]:
    """Similarity search in the session's Qdrant collection; [] if none exists."""
    from langchain_qdrant import QdrantVectorStore
    from qdrant_client import QdrantClient

    from app.infra.vector_store import embeddings

    client = QdrantClient(url=settings._qdrant_url)
    if not client.collection_exists(session_id):
        return []
    store = QdrantVectorStore(client=client, collection_name=session_id, embedding=embeddings)
    return [(d.page_content, dict(d.metadata or {})) for d in store.similarity_search(question, k=k)]


def retrieve_passages(
    session_id: str, question: str, client_ids: Sequence[str], k: int
) -> list[RetrievedChunk]:
    files = session_documents(session_id)
    selected = select_documents(files, client_ids)
    if not selected:
        return []
    # Over-fetch: chunks of unselected files share the collection.
    hits = search_session(session_id, question, k * 3)
    return attribute_hits(hits, selected, files)[:k]


def document_text(session_id: str, file_id: str) -> str:
    from app.infra.minio_client import minio_client

    path = f"{session_id}/{file_id}_docs.txt"
    if not minio_client.file_exists(path):
        return ""
    data = minio_client.download_data(path) or b""
    return data.decode("utf-8", errors="replace")[:MAX_DOCUMENT_CHARS]


def whole_documents(session_id: str, client_ids: Sequence[str]) -> list[RetrievedChunk]:
    """One chunk per selected document holding its (truncated) parsed text."""
    chunks: list[RetrievedChunk] = []
    for doc in select_documents(session_documents(session_id), client_ids):
        text = document_text(session_id, doc.file_id).strip()
        if text:
            chunks.append(
                {"file_id": doc.file_id, "file_name": doc.file_name, "page": None, "text": text}
            )
    return chunks


def selected_document_ids(session_id: str, client_ids: Sequence[str]) -> list[str]:
    return [d.file_id for d in select_documents(session_documents(session_id), client_ids)]
