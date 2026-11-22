"""PDF parsing must fail loudly and must not reserve the model's whole output window.

Seen live: OpenRouter answered 402 ("You requested up to 65535 tokens, but can only
afford 11303") because no max_tokens was sent; the failed chunk was then stored as
"[ERROR: Failed to parse chunk 0]" and the file was marked processed for good.
"""

from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.infra import vector_store


class _Completions:
    def __init__(self, fail=False):
        self.fail = fail
        self.kwargs = []

    def create(self, **kwargs):
        self.kwargs.append(kwargs)
        if self.fail:
            raise RuntimeError("Error code: 402 - requires more credits")
        message = SimpleNamespace(content="# Trang\nnội dung")
        return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")])


@pytest.fixture
def completions(monkeypatch):
    fake = _Completions()
    monkeypatch.setattr(vector_store, "openrouter_client", SimpleNamespace(chat=SimpleNamespace(completions=fake)))
    monkeypatch.setattr(vector_store, "encode_pdf_pages", lambda path: ["p1", "p2"])
    monkeypatch.setattr(settings, "PDF_PARSE_RETRY_ATTEMPTS", 1)
    monkeypatch.setattr(settings, "PDF_PARSE_RETRY_DELAY", 0)
    return fake


def test_parse_request_caps_the_output_tokens(completions):
    assert vector_store.parse_pdf_parallel("x.pdf") == "# Trang\nnội dung"
    assert completions.kwargs[0]["max_tokens"] == settings.PDF_PARSE_MAX_TOKENS


def test_a_chunk_that_cannot_be_parsed_fails_the_whole_parse(completions):
    completions.fail = True
    with pytest.raises(vector_store.PdfParseError):
        vector_store.parse_pdf_parallel("x.pdf")
