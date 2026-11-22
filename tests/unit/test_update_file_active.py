"""Switching a file on parses and embeds it once; a failed parse must not count.

Seen live: the parse failed (OpenRouter 402), yet the file was marked
``has_processed`` with "[ERROR: Failed to parse chunk 0]" as its text, so it
could never be processed again and every feature saw an empty document.
"""

import asyncio
import inspect

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.api.v1 import upload
from app.core.config import settings
from app.db.models.upload import UploadFileStatus
from app.infra.vector_store import PdfParseError


class FakeMinio:
    def __init__(self):
        self.objects: dict[str, bytes] = {"s1/a.pdf": b"%PDF"}

    def download_file(self, name, local_path):
        with open(local_path, "wb") as f:
            f.write(self.objects[name])
        return True

    def upload_file(self, local_path, name):
        with open(local_path, "rb") as f:
            self.objects[name] = f.read()
        return True

    def file_exists(self, name):
        return name in self.objects

    def download_data(self, name):
        return self.objects.get(name)


@pytest.fixture
def env(monkeypatch, tmp_path):
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine, tables=[UploadFileStatus.__table__])
    with Session(engine) as db:
        db.add(UploadFileStatus(file_id="f1", session_id="s1", file_name="a.pdf"))
        db.commit()
    # Private attrs live in __pydantic_private__ (see test_agui_auth).
    monkeypatch.setitem(settings.__pydantic_private__, "_app_db_engine", engine)
    minio = FakeMinio()
    monkeypatch.setattr(upload, "minio_client", minio)
    monkeypatch.setattr(upload, "TMP_DIR", str(tmp_path))
    state = {"parse": "# Bài\nnội dung", "embedded": []}

    def parse(file_path, max_workers=None):
        if isinstance(state["parse"], Exception):
            raise state["parse"]
        return state["parse"]

    monkeypatch.setattr(upload, "parse_pdf_parallel", parse)
    monkeypatch.setattr(upload, "embedding_document", lambda docs, sid, **kw: state["embedded"].append(docs))

    def record():
        with Session(engine) as db:
            return db.exec(select(UploadFileStatus)).one()

    return state, minio, record


def _activate():
    result = upload.update_file_active(file_id="f1", active=True)
    return asyncio.run(result) if inspect.isawaitable(result) else result


def test_failed_parse_reports_an_error_and_is_not_marked_processed(env):
    state, minio, record = env
    state["parse"] = PdfParseError("chunk 0 could not be parsed: 402")
    out = _activate()
    assert out["has_processed"] is False and out["error"]
    assert "402" not in out["error"]  # provider details stay in the log
    assert record().has_processed is False
    assert state["embedded"] == [] and "s1/f1_docs.txt" not in minio.objects


def test_switching_on_again_after_a_failure_retries_the_parse(env):
    state, minio, record = env
    state["parse"] = PdfParseError("402")
    _activate()
    state["parse"] = "# Bài\nnội dung"
    out = _activate()
    assert out["has_processed"] is True and "error" not in out
    assert record().has_processed is True
    assert minio.objects["s1/f1_docs.txt"] == "# Bài\nnội dung".encode()
    assert len(state["embedded"]) == 1


def test_a_file_processed_before_with_only_parse_error_markers_is_processed_again(env):
    state, minio, record = env
    with Session(settings._app_db_engine) as db:
        row = db.exec(select(UploadFileStatus)).one()
        row.has_processed = True
        db.add(row)
        db.commit()
    minio.objects["s1/f1_docs.txt"] = b"[ERROR: Failed to parse chunk 0]"
    out = _activate()
    assert out["has_processed"] is True
    assert minio.objects["s1/f1_docs.txt"] == "# Bài\nnội dung".encode()
    assert len(state["embedded"]) == 1


def test_a_file_already_processed_is_not_parsed_again(env):
    state, minio, record = env
    _activate()
    _activate()
    assert len(state["embedded"]) == 1


def test_parsing_runs_off_the_event_loop():
    """An ``async def`` route that parses for 20s+ freezes every other request."""
    assert not inspect.iscoroutinefunction(upload.update_file_active)
