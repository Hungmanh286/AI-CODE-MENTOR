"""Reading a cropped image must cap the output like every other OpenRouter call
(no max_tokens = the provider reserves the whole window and answers 402 when
credits are low)."""

from types import SimpleNamespace

from app.agents.feedback_answer import graph as feedback_graph


def test_image_to_text_caps_the_output_tokens(monkeypatch, tmp_path):
    seen = {}

    def create(**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="int x = 1;"))])

    monkeypatch.setattr(feedback_graph, "OpenAI",
                        lambda **kw: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    image = tmp_path / "crop.jpg"
    image.write_bytes(b"\xff\xd8fake")
    assert feedback_graph.image_to_text(str(image)) == "int x = 1;"
    assert seen["max_tokens"] == feedback_graph.IMAGE_TO_TEXT_MAX_TOKENS
