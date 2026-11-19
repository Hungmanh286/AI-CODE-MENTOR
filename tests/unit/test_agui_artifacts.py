"""Quizzes and mind maps produced by the AG-UI agent are stored where the rest
of the app reads them (BACKEND-PLAN GĐ3.1 / GĐ3.2 / GĐ3.3)."""

import json

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.agents.mentor_agui.ui_catalog import MindmapNode, QuizQuestion, ShowMindmap, ShowQuiz
from app.db.models.agent_mindmap import AgentMindMap
from app.db.models.question import Project, Question, QuestionOption
from app.services import agui_artifacts


@pytest.fixture
def engine():
    eng = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(
        eng,
        tables=[t.__table__ for t in (Project, Question, QuestionOption, AgentMindMap)],
    )
    return eng


def _quiz(n=2) -> ShowQuiz:
    return ShowQuiz(
        title="Kế thừa",
        questions=[
            QuizQuestion(id=f"q{i + 1}", question=f"Câu {i}?", options=["a", "b", "c"], answer_index=i % 3,
                         explanation=f"vì {i}", difficulty="hard")
            for i in range(n)
        ],
    )


def test_save_quiz_writes_project_questions_and_options(engine):
    project_id, saved = agui_artifacts.save_quiz("s1", _quiz(), source_path="s1/oop.pdf", engine=engine)
    with Session(engine) as db:
        project = db.get(Project, project_id)
        questions = db.exec(select(Question).where(Question.project_id == project_id)).all()
        options = db.exec(select(QuestionOption)).all()
    assert project.session_id == "s1" and project.name == "Kế thừa" and project.source_path == "s1/oop.pdf"
    assert sorted((q.question_id, q.correct_answer, q.difficulty) for q in questions) == [
        ("q1", 0, "hard"),
        ("q2", 1, "hard"),
    ]
    assert len(options) == 6
    # show_quiz ids are the DB ids, so the frontend can call /add_answer/{qid}
    assert {q.id for q in saved.questions} == {q.id for q in questions}
    assert [q.question for q in saved.questions] == ["Câu 0?", "Câu 1?"]


def test_save_mindmap_stores_the_tree(engine):
    tree = ShowMindmap(title="OOP", root=MindmapNode(id="n", label="OOP", children=[MindmapNode(id="n_1", label="Đa hình")]))
    mindmap_id = agui_artifacts.save_mindmap("s1", tree, engine=engine)
    with Session(engine) as db:
        row = db.get(AgentMindMap, mindmap_id)
    assert row.session_id == "s1" and row.title == "OOP"
    assert json.loads(row.tree_json)["root"]["children"][0]["label"] == "Đa hình"


def test_session_artifacts_lists_this_session_quizzes_with_counts_and_mindmaps(engine):
    p1, _ = agui_artifacts.save_quiz("s1", _quiz(2), engine=engine)
    p2, _ = agui_artifacts.save_quiz("s1", _quiz(3), engine=engine)
    agui_artifacts.save_quiz("other", _quiz(1), engine=engine)
    m1 = agui_artifacts.save_mindmap("s1", ShowMindmap(title="Sơ đồ", root=MindmapNode(id="n", label="x")), engine=engine)
    artifacts = agui_artifacts.session_artifacts("s1", engine=engine)
    assert artifacts == {
        "quizzes": [
            {"id": p1, "title": "Kế thừa", "count": 2},
            {"id": p2, "title": "Kế thừa", "count": 3},
        ],
        "mindmaps": [{"id": m1, "title": "Sơ đồ"}],
    }


def test_session_artifacts_of_unknown_session_is_empty(engine):
    assert agui_artifacts.session_artifacts("nope", engine=engine) == {"quizzes": [], "mindmaps": []}
