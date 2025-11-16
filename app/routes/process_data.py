import os
import json
import uuid

from fastapi import APIRouter, Form, HTTPException
from sqlmodel import SQLModel, Session, select, delete
from langfuse.callback import CallbackHandler
from langchain_core.runnables.config import RunnableConfig

from app.graph.agents.question_expert import question_expert, UPLOAD_DIR  # noqa
from app.graph.agents.document_processing import document_processing_agent
from app.schema.question import Project, Question, QuestionOption
from app.services.datasource import insert_database
from app.schema.question import SessionProject
from app.services.datasource import get_active_file_id
from app.config import settings

router = APIRouter()

tracer = CallbackHandler(
    tags=["code"],
    public_key=settings.LANGFUSE_PUBLIC_KEY,
    secret_key=settings.LANGFUSE_SECRET_KEY,
    host=settings.LANGFUSE_HOST,
)


@router.post("/process")
async def process_pdf(
    session_id: str = Form(...),
):
    # Gọi question_expert để xử lý PDF và sinh câu hỏi
    config = RunnableConfig(configurable={"thread_id": session_id}, callbacks=[tracer])
    result = await document_processing_agent.ainvoke({}, config)
    evaluated_result = result["quizz"]
    questions_data = json.loads(evaluated_result)

    file_ids = get_active_file_id(session_id)
    file_id = file_ids[0] if file_ids else None
    session_folder = os.path.join(UPLOAD_DIR, session_id)
    latest_file = os.path.join(session_folder, f"{file_id}_{session_id}_latest.txt")
    if os.path.exists(latest_file):
        with open(latest_file, "r") as f:
            file_path = f.read().strip()
        file_name = os.path.basename(file_path)

    # Tạo project mới
    project_id = str(uuid.uuid4())
    project_data = {
        "id": project_id,
        "session_id": session_id,
        "name": file_name,
        "source_path": os.path.join(session_folder, f"{session_id}_latest.txt"),
    }

    # Lưu project vào database
    insert_database(project_data, Project)
    # Lưu session-project vào database
    from app.schema.question import SessionProject

    session_project_data = {"session_id": session_id, "project_id": project_id}
    insert_database(session_project_data, SessionProject)

    # Lưu từng câu hỏi và các lựa chọn vào database
    for q in questions_data:
        # Tạo câu hỏi
        question_id = str(uuid.uuid4())
        question_data = {
            "id": question_id,
            "project_id": project_id,
            "question_id": q["id"],
            "question": q["question"],
            "type": q["type"],
            "difficulty": q.get("difficulty"),
            "correct_answer": q.get("correct_answer"),
            "explanation": q.get("explanation"),
        }

        # Lưu câu hỏi vào database
        insert_database(question_data, Question)

        # Lưu các option của câu hỏi
        for idx, option_text in enumerate(q.get("options", [])):
            option_data = {
                "question_id": question_id,
                "option_index": idx,
                "option_text": option_text,
            }
            insert_database(option_data, QuestionOption)

    return {
        "project_id": project_id,
        "questions": questions_data,
        "message": f"Đã lưu {len(questions_data)} câu hỏi vào database",
    }


@router.post("/create-session")
def create_session(session_id: str = Form(...), project_id: str = Form(None)):
    session_project_data = {"session_id": session_id, "project_id": project_id}
    insert_database(session_project_data, SessionProject)
    return {
        "message": "Session created successfully",
        "session_id": session_id,
        "project_id": project_id,
    }


@router.get("/session-projects/{session_id}")
def get_projects_by_session(session_id: str):
    from app.services.datasource import settings as ds_settings

    engine = ds_settings._app_db_engine
    with Session(engine) as session:
        session_projects = session.exec(
            select(SessionProject).where(SessionProject.session_id == session_id)
        ).all()
        project_ids = [sp.project_id for sp in session_projects]
        projects = session.exec(
            select(Project).where(Project.id.in_(project_ids))
        ).all()
        return {"projects": [p.dict() for p in projects]}


@router.get("/project-questions/{project_id}")
def get_questions_by_project(project_id: str):
    from app.services.datasource import settings as ds_settings

    engine = ds_settings._app_db_engine
    with Session(engine) as session:
        questions = session.exec(
            select(Question).where(Question.project_id == project_id)
        ).all()
        result = []
        for q in questions:
            options = session.exec(
                select(QuestionOption).where(QuestionOption.question_id == q.id)
            ).all()
            result.append(
                {
                    "id": q.id,
                    "question": q.question,
                    "type": q.type,
                    "difficulty": q.difficulty,
                    "correct_answer": q.correct_answer,
                    "explanation": q.explanation,
                    "options": [opt.option_text for opt in options],
                }
            )
        return {"questions": result}


@router.post("/add_answer/{question_id}")
def add_answer_to_question(question_id: str, answer: int = Form(...)):
    from app.services.datasource import settings as ds_settings

    engine = ds_settings._app_db_engine
    with Session(engine) as session:
        question = session.get(Question, question_id)
        if not question:
            raise HTTPException(status_code=404, detail="Question not found")

        # Cập nhật answer
        question.answer = answer

        # So sánh answer với correct_answer để tính score
        if question.correct_answer is not None and answer == question.correct_answer:
            question.score = 1
        else:
            question.score = 0

        session.add(question)
        session.commit()
        session.refresh(question)
        return {
            "message": "Answer added successfully",
            "question_id": question_id,
            "answer": answer,
            "score": question.score,
        }


@router.get("/sessions")
def get_all_sessions():
    try:
        from app.services.datasource import settings as ds_settings

        engine = ds_settings._app_db_engine
        from app.schema.question import SessionProject

        # Đảm bảo bảng tồn tại trước khi truy vấn
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            sessions = session.exec(select(SessionProject.session_id)).all()
            # Loại bỏ trùng lặp
            unique_sessions = list(set(sessions))
            return {"sessions": unique_sessions}
    except Exception:
        pass


@router.delete("/sessions/{session_id}")
def delete_session_data(session_id: str):
    from app.services.datasource import settings as ds_settings
    from app.schema.upload import UploadFileStatus

    engine = ds_settings._app_db_engine
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session_projects = session.exec(
            select(SessionProject).where(SessionProject.session_id == session_id)
        ).all()
        if not session_projects:
            raise HTTPException(status_code=404, detail="Session not found")
        projects = session.exec(
            select(Project).where(
                (Project.session_id == session_id) & (Project.id.is_not(None))
            )
        ).all()
        project_ids = [p.id for p in projects]
        questions = session.exec(
            select(Question).where(Question.project_id.in_(project_ids))
        ).all()
        question_ids = [q.id for q in questions]
        if question_ids:
            session.exec(
                delete(QuestionOption).where(
                    QuestionOption.question_id.in_(question_ids)
                )
            )
        if project_ids:
            session.exec(delete(Question).where(Question.project_id.in_(project_ids)))
        if project_ids:
            session.exec(delete(Project).where(Project.session_id == session_id))
        session.exec(
            delete(SessionProject).where(SessionProject.session_id == session_id)
        )
        session.exec(
            delete(UploadFileStatus).where(UploadFileStatus.session_id == session_id)
        )
        session.commit()
        # Xóa folder chứa file của session
        session_folder = os.path.join(UPLOAD_DIR, session_id)
        if os.path.exists(session_folder):
            import shutil

            shutil.rmtree(session_folder)
        return {"detail": f"Deleted all data for session_id: {session_id}"}
