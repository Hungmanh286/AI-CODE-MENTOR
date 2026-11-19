"""Storage of what the AG-UI agent produces (BACKEND-PLAN GĐ3).

* Quizzes go to the existing ``projects`` / ``questions`` / ``question_options``
  tables, so ``/session-projects``, ``/project-questions`` and
  ``/project-scores`` see them; ``show_quiz`` uses the DB question ids so the
  frontend can later post answers to ``/add_answer/{qid}``.
* Mind maps go to ``agent_mindmaps`` as the ``show_mindmap`` JSON tree.
* ``session_artifacts`` is the source of truth for ``artifacts`` in the shared
  state (contract 4.7): it is projected into the graph state at the start of
  each run and into ``GET /threads/{id}/messages``.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import func
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from app.core.config import settings
from app.db.models.agent_mindmap import AgentMindMap
from app.db.models.question import Project, Question, QuestionOption

if TYPE_CHECKING:  # runtime import would be circular (the agent imports this module)
    from app.agents.mentor_agui.ui_catalog import ShowMindmap, ShowQuiz

QUESTION_TYPE = "multiple_choice"


def _engine(engine: Engine | None) -> Engine:
    return engine if engine is not None else settings._app_db_engine


def save_quiz(
    session_id: str, quiz: ShowQuiz, *, source_path: str | None = None, engine: Engine | None = None
) -> tuple[str, ShowQuiz]:
    """Store ``quiz`` as a project; return ``(project_id, quiz with DB question ids)``."""
    project_id = str(uuid.uuid4())
    db_ids = [str(uuid.uuid4()) for _ in quiz.questions]
    with Session(_engine(engine)) as db:
        db.add(Project(id=project_id, session_id=session_id, name=quiz.title, source_path=source_path))
        db.flush()  # the project row must exist before questions reference it
        for db_id, q in zip(db_ids, quiz.questions, strict=True):
            db.add(
                Question(
                    id=db_id,
                    project_id=project_id,
                    question_id=q.id,
                    question=q.question,
                    type=QUESTION_TYPE,
                    difficulty=q.difficulty,
                    correct_answer=q.answer_index,
                    explanation=q.explanation,
                )
            )
        db.flush()
        for db_id, q in zip(db_ids, quiz.questions, strict=True):
            for index, text in enumerate(q.options):
                db.add(QuestionOption(question_id=db_id, option_index=index, option_text=text))
        db.commit()
    saved = quiz.model_copy(
        update={
            "questions": [
                q.model_copy(update={"id": db_id}) for db_id, q in zip(db_ids, quiz.questions, strict=True)
            ]
        }
    )
    return project_id, saved


def save_mindmap(session_id: str, mindmap: ShowMindmap, *, engine: Engine | None = None) -> str:
    row = AgentMindMap(
        session_id=session_id,
        title=mindmap.title,
        tree_json=mindmap.model_dump_json(exclude_none=True),
    )
    with Session(_engine(engine)) as db:
        db.add(row)
        db.commit()
        return row.id


def session_artifacts(session_id: str, *, engine: Engine | None = None) -> dict[str, list[dict]]:
    """``{"quizzes": [{id, title, count}], "mindmaps": [{id, title}]}``, oldest first."""
    with Session(_engine(engine)) as db:
        counts = (
            select(Question.project_id, func.count(Question.id).label("n"))
            .group_by(Question.project_id)
            .subquery()
        )
        quiz_rows = db.exec(
            select(Project.id, Project.name, func.coalesce(counts.c.n, 0))
            .join(counts, counts.c.project_id == Project.id, isouter=True)
            .where(Project.session_id == session_id)
            .order_by(Project.created_at, Project.id)
        ).all()
        mindmap_rows = db.exec(
            select(AgentMindMap.id, AgentMindMap.title)
            .where(AgentMindMap.session_id == session_id)
            .order_by(AgentMindMap.created_at, AgentMindMap.id)
        ).all()
    return {
        "quizzes": [{"id": pid, "title": name, "count": int(n)} for pid, name, n in quiz_rows],
        "mindmaps": [{"id": mid, "title": title} for mid, title in mindmap_rows],
    }

