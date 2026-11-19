"""Real LLM/RAG wiring of the AG-UI agent (BACKEND-PLAN GĐ2), without network.

The LLM is replaced by a scripted structured-output caller; what is tested is
our code around it: turning model drafts into exact contract payloads (4.5),
retries, document selection and citation attribution.
"""

import asyncio

import pytest

from app.agents.mentor_agui.backends import MentorBackend
from app.agents.mentor_agui.schemas import (
    FollowupsDraft,
    IntentDraft,
    MindmapDraft,
    MindmapDraftNode,
    QuizDraft,
    QuizDraftQuestion,
    clean_followups,
    mindmap_from_draft,
    quiz_from_draft,
)
from app.agents.mentor_agui.ui_catalog import ShowMindmap, ShowQuiz
from app.services.agui_documents import DocRef, attribute_hits, select_documents


def _q(i: int, answer: int = 1, options=None) -> QuizDraftQuestion:
    return QuizDraftQuestion(
        question=f"Câu hỏi {i}?",
        options=options if options is not None else ["A", "B", "C", "D"],
        answer_index=answer,
        explanation=f"Giải thích {i}",
    )


# --- quiz ----------------------------------------------------------------


def test_quiz_from_draft_returns_exactly_count_questions_with_ids_and_difficulty():
    draft = QuizDraft(title="OOP", questions=[_q(i) for i in range(5)])
    quiz = quiz_from_draft(draft, count=3, difficulty="hard")
    assert isinstance(quiz, ShowQuiz)
    assert [q.id for q in quiz.questions] == ["q1", "q2", "q3"]
    assert {q.difficulty for q in quiz.questions} == {"hard"}


def test_quiz_from_draft_drops_invalid_questions_before_counting():
    draft = QuizDraft(
        title="OOP",
        questions=[_q(0, answer=7), _q(1, options=["Chỉ một"]), _q(2), _q(3)],
    )
    quiz = quiz_from_draft(draft, count=2, difficulty="easy")
    assert [q.question for q in quiz.questions] == ["Câu hỏi 2?", "Câu hỏi 3?"]


def test_quiz_from_draft_raises_when_too_few_valid_questions():
    draft = QuizDraft(title="OOP", questions=[_q(0), _q(1, answer=-1)])
    with pytest.raises(ValueError):
        quiz_from_draft(draft, count=2, difficulty="medium")


# --- mindmap -------------------------------------------------------------


def _chain(depth: int) -> MindmapDraftNode:
    node = MindmapDraftNode(label=f"L{depth}")
    for d in range(depth - 1, 0, -1):
        node = MindmapDraftNode(label=f"L{d}", children=[node])
    return node


def _depth(node) -> int:
    return 1 + max((_depth(c) for c in node.children or []), default=0)


def test_mindmap_from_draft_caps_depth_at_six_levels():
    result = mindmap_from_draft(MindmapDraft(title="Sâu", root=_chain(9)))
    assert isinstance(result, ShowMindmap)
    assert _depth(result.root) == 6


def test_mindmap_from_draft_assigns_unique_ids_and_omits_empty_children():
    root = MindmapDraftNode(
        label="OOP",
        children=[
            MindmapDraftNode(label="Kế thừa", children=[MindmapDraftNode(label="extends")]),
            MindmapDraftNode(label="  "),  # blank label is dropped
            MindmapDraftNode(label="Đa hình"),
        ],
    )
    result = mindmap_from_draft(MindmapDraft(title="OOP", root=root))
    ids, stack = [], [result.root]
    while stack:
        node = stack.pop()
        ids.append(node.id)
        stack.extend(node.children or [])
    assert len(ids) == len(set(ids)) == 4
    assert [c.label for c in result.root.children] == ["Kế thừa", "Đa hình"]
    assert result.root.children[1].children is None


# --- follow-ups ----------------------------------------------------------


def test_clean_followups_strips_dedupes_and_keeps_three():
    out = clean_followups([" A? ", "A?", "", "B?", "C?", "D?"])
    assert out == ["A?", "B?", "C?"]


# --- documents -----------------------------------------------------------

FILES = [
    DocRef(file_id="f1", file_name="oop.pdf", active=True, has_processed=True),
    DocRef(file_id="f2", file_name="java.pdf", active=False, has_processed=True),
    DocRef(file_id="f3", file_name="c.pdf", active=True, has_processed=False),
]


def test_select_documents_uses_active_files_when_client_sends_none():
    assert [d.file_id for d in select_documents(FILES, [])] == ["f1", "f3"]


def test_select_documents_only_accepts_ids_of_this_session():
    assert [d.file_id for d in select_documents(FILES, ["f2", "other-session"])] == ["f2"]


def test_attribute_hits_keeps_chunks_of_selected_documents_only():
    hits = [("đa hình", {"file_id": "f1"}), ("java", {"file_id": "f2"}), ("?", {"Header_1": "x"})]
    chunks = attribute_hits(hits, select_documents(FILES, ["f1"]), FILES)
    assert chunks == [{"file_id": "f1", "file_name": "oop.pdf", "page": None, "text": "đa hình"}]


def test_attribute_hits_attributes_legacy_chunks_only_when_unambiguous():
    single = [DocRef(file_id="f1", file_name="oop.pdf", active=True, has_processed=True)]
    hits = [("legacy chunk", {"Header_1": "Bài 1"})]
    assert attribute_hits(hits, single, single)[0]["file_id"] == "f1"
    # two processed files share the collection: a chunk without file_id is ambiguous
    assert attribute_hits(hits, select_documents(FILES, ["f1"]), FILES) == []


# --- backend (scripted structured output) --------------------------------


class ScriptedStructured:
    """Returns the next scripted draft for each structured call."""

    def __init__(self, *drafts):
        self.drafts = list(drafts)
        self.calls = []

    async def __call__(self, schema, messages, config):
        self.calls.append(schema)
        return self.drafts.pop(0)


def _backend(structured) -> MentorBackend:
    return MentorBackend(chat_model_factory=lambda: None, structured_call=structured)


def test_generate_quiz_retries_until_count_is_met():
    structured = ScriptedStructured(
        QuizDraft(title="OOP", questions=[_q(0)]),
        QuizDraft(title="OOP", questions=[_q(i) for i in range(3)]),
    )
    quiz = asyncio.run(_backend(structured).generate_quiz("oop", [], 3, "medium", {}))
    assert len(quiz.questions) == 3 and len(structured.calls) == 2


def test_generate_quiz_gives_up_after_retries():
    structured = ScriptedStructured(*[QuizDraft(title="x", questions=[]) for _ in range(5)])
    with pytest.raises(ValueError):
        asyncio.run(_backend(structured).generate_quiz("oop", [], 3, "medium", {}))


def test_classify_and_followups_use_structured_drafts():
    structured = ScriptedStructured(
        IntentDraft(intent="mindmap"), FollowupsDraft(questions=["a?", "a?", "b?"])
    )
    backend = _backend(structured)
    assert asyncio.run(backend.classify_intent("vẽ sơ đồ", [], {})) == "mindmap"
    assert asyncio.run(backend.suggest_followups("q", "a", {})) == ["a?", "b?"]
