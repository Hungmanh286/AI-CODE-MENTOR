"""Chunks embedded for a file carry its id/name so the AG-UI agent can cite them."""

from app.infra.vector_store import split_markdown


def test_split_markdown_stamps_file_metadata_on_every_chunk():
    docs = ["# Bài 1\nĐa hình là ...\n## Kế thừa\nextends ..."]
    splits = split_markdown(docs, file_id="f1", file_name="oop.pdf")
    assert len(splits) == 2
    assert all(s.metadata["file_id"] == "f1" and s.metadata["file_name"] == "oop.pdf" for s in splits)
    assert splits[1].metadata["Header_2"] == "Kế thừa"


def test_split_markdown_without_file_keeps_header_metadata_only():
    splits = split_markdown(["# A\nx"])
    assert splits[0].metadata == {"Header_1": "A"}
