"""Structured-output schemas asked from the LLM, and their conversion to the
exact UI tool payloads of ``ui_catalog`` (contract 4.5).

The LLM never produces ids, difficulty or depth limits: those are set here, so
a model mistake cannot break the frontend contract. Drafts are permissive
(no ``extra="forbid"``, no cross-field validators) to keep the JSON schema
simple for providers; ``*_from_draft`` does the strict checking.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .ui_catalog import MindmapNode, QuizQuestion, ShowMindmap, ShowQuiz

Intent = Literal["ask", "summarize", "mindmap", "mcq", "other"]
Difficulty = Literal["easy", "medium", "hard"]

MAX_MINDMAP_DEPTH = 6  # frontend MindmapView renders at most 6 levels
MAX_FOLLOWUPS = 3


class IntentDraft(BaseModel):
    """Intent of the learner's latest message."""

    intent: Intent = Field(
        description=(
            "ask: hỏi/giải thích kiến thức; summarize: tóm tắt tài liệu; "
            "mindmap: vẽ sơ đồ tư duy; mcq: tạo câu hỏi trắc nghiệm/quiz; other: còn lại"
        )
    )


MAX_QUIZ_COUNT = 30  # QuizConfigPayload.count upper bound (graph.py)


class QuizRequestDraft(BaseModel):
    """Quiz parameters the learner stated in the message (null when not stated)."""

    topic: str | None = Field(
        default=None,
        description=(
            "Chủ đề cần hỏi, không kèm số câu/độ khó/từ 'tạo câu hỏi' (vd: 'toán lớp 1'). "
            "null nếu không nêu chủ đề (vd: 'tạo quiz', 'tạo câu hỏi từ tài liệu')."
        ),
    )
    count: int | None = Field(default=None, description="Số câu hỏi người học nêu; null nếu không nêu.")
    difficulty: Difficulty | None = Field(
        default=None, description="easy=dễ, medium=vừa, hard=khó; null nếu không nêu."
    )


def quiz_request_from_draft(draft: QuizRequestDraft) -> dict:
    """``{topic, count, difficulty}`` with an empty topic as None and count in 1..30."""
    topic = (draft.topic or "").strip() or None
    count = draft.count if draft.count and draft.count > 0 else None
    return {
        "topic": topic,
        "count": min(count, MAX_QUIZ_COUNT) if count else None,
        "difficulty": draft.difficulty,
    }


class FollowupsDraft(BaseModel):
    """Short follow-up questions the learner could ask next."""

    questions: list[str] = Field(description="Tối đa 3 câu hỏi ngắn bằng tiếng Việt")


class QuizDraftQuestion(BaseModel):
    question: str
    options: list[str] = Field(description="4 lựa chọn, không có tiền tố A./B./C./D.")
    answer_index: int = Field(description="Chỉ số (từ 0) của đáp án đúng trong options")
    explanation: str = Field(description="Giải thích ngắn vì sao đáp án đúng")


class QuizDraft(BaseModel):
    """A multiple-choice quiz."""

    title: str
    questions: list[QuizDraftQuestion]


class MindmapDraftNode(BaseModel):
    label: str
    children: list[MindmapDraftNode] = Field(default_factory=list)


MindmapDraftNode.model_rebuild()


class MindmapDraft(BaseModel):
    """A mind map as a tree of short labels."""

    title: str
    root: MindmapDraftNode


def _valid_question(q: QuizDraftQuestion) -> bool:
    options = [o.strip() for o in q.options]
    return (
        bool(q.question.strip())
        and len(options) >= 2
        and all(options)
        and len(set(options)) == len(options)
        and 0 <= q.answer_index < len(options)
    )


def quiz_from_draft(draft: QuizDraft, count: int, difficulty: Difficulty) -> ShowQuiz:
    """Exactly ``count`` valid questions, ids ``q1..qN``, the requested difficulty.

    Raises ``ValueError`` when the draft has fewer than ``count`` valid questions.
    """
    valid = [q for q in draft.questions if _valid_question(q)]
    if len(valid) < count:
        raise ValueError(f"quiz draft has {len(valid)} valid questions, {count} requested")
    questions = [
        QuizQuestion(
            id=f"q{i + 1}",
            question=q.question.strip(),
            options=[o.strip() for o in q.options],
            answer_index=q.answer_index,
            explanation=q.explanation.strip(),
            difficulty=difficulty,
        )
        for i, q in enumerate(valid[:count])
    ]
    return ShowQuiz(title=draft.title.strip() or "Bài kiểm tra", questions=questions)


def _node(draft: MindmapDraftNode, node_id: str, depth: int, max_depth: int) -> MindmapNode:
    children: list[MindmapNode] = []
    if depth < max_depth:
        kept = [c for c in draft.children if c.label.strip()]
        children = [
            _node(child, f"{node_id}_{i + 1}", depth + 1, max_depth) for i, child in enumerate(kept)
        ]
    return MindmapNode(id=node_id, label=draft.label.strip(), children=children or None)


def mindmap_from_draft(draft: MindmapDraft, max_depth: int = MAX_MINDMAP_DEPTH) -> ShowMindmap:
    """Tree with unique path ids (``n``, ``n_1``, ``n_1_2`` ...) and depth <= ``max_depth``."""
    if not draft.root.label.strip():
        raise ValueError("mindmap root has no label")
    return ShowMindmap(
        title=draft.title.strip() or draft.root.label.strip(),
        root=_node(draft.root, "n", 1, max_depth),
    )


def clean_followups(questions: list[str], limit: int = MAX_FOLLOWUPS) -> list[str]:
    out: list[str] = []
    for q in questions:
        text = q.strip()
        if text and text not in out:
            out.append(text)
    return out[:limit]


__all__ = [
    "FollowupsDraft",
    "IntentDraft",
    "MindmapDraft",
    "MindmapDraftNode",
    "QuizDraft",
    "QuizDraftQuestion",
    "clean_followups",
    "mindmap_from_draft",
    "quiz_from_draft",
]
