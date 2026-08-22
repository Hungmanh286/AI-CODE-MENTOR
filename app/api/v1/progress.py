from fastapi import APIRouter
from sqlmodel import Session, select

from app.db.models.question import Project, Question

router = APIRouter()


@router.get("/project-scores")
def get_project_scores():
    from app.db.datasource import settings as ds_settings

    engine = ds_settings._app_db_engine
    with Session(engine) as session:
        # Lấy tất cả project
        projects = session.exec(select(Project)).all()

        result = []
        for project in projects:
            # Lấy tất cả question theo project_id
            questions = session.exec(
                select(Question).where(Question.project_id == project.id)
            ).all()

            # Tính tổng score
            total_score = sum(q.score for q in questions if q.score is not None)

            result.append(
                {
                    "project_id": project.id,
                    "project_name": project.name,
                    "session_id": project.session_id,
                    "total_score": total_score,
                    "total_questions": len(questions),
                }
            )

        return {"projects": result}


@router.get("/project-questions-detail/{project_id}")
def get_questions_detail_by_project(project_id: str):
    from app.db.datasource import settings as ds_settings

    engine = ds_settings._app_db_engine
    with Session(engine) as session:
        questions = session.exec(
            select(Question).where(Question.project_id == project_id)
        ).all()
        result = []
        for q in questions:
            result.append(
                {
                    "id": q.id,
                    "difficulty": q.difficulty,
                    "correct_answer": q.correct_answer,
                    "explanation": q.explanation,
                    "answer": q.answer,
                }
            )
        return {"questions": result}
