
import structlog
from fastapi import APIRouter, Form, HTTPException, Query
from langfuse.langchain import CallbackHandler
from sqlmodel import Session, SQLModel, delete, select

from app.db.datasource import insert_database
from app.db.models.question import Project, Question, QuestionOption, SessionProject
from app.infra.minio_client import minio_client

logger = structlog.get_logger(__name__)

router = APIRouter()

tracer = CallbackHandler()



@router.post("/create-session")
def create_session(
    session_id: str = Form(...),
    user_id: str = Form(None),
    project_id: str = Form(None),
    session_name: str = Form(None),
):
    # Set defaults if not provided
    if not user_id:
        user_id = "default"
    if not session_name:
        session_name = f"Session {session_id[:8]}"

    session_project_data = {
        "session_id": session_id,
        "user_id": user_id,
        "project_id": project_id,
        "session_name": session_name,
    }
    insert_database(session_project_data, SessionProject)
    return {
        "message": "Session created successfully",
        "session_id": session_id,
        "user_id": user_id,
        "session_name": session_name,
        "project_id": project_id,
    }


@router.get("/sessions")
def get_all_sessions():
    """
    Lấy tất cả sessions
    """
    from app.db.datasource import settings as ds_settings

    engine = ds_settings._app_db_engine
    with Session(engine) as session:
        all_sessions = session.exec(select(SessionProject)).all()
        result = [sp.session_id for sp in all_sessions]
        return {"sessions": result}


@router.get("/user-sessions/{user_id}")
def get_sessions_by_user(user_id: str):
    """
    Lấy tất cả sessions của một user cụ thể
    """
    from app.db.datasource import settings as ds_settings

    engine = ds_settings._app_db_engine
    with Session(engine) as session:
        user_sessions = session.exec(
            select(SessionProject).where(SessionProject.user_id == user_id)
        ).all()
        result = [
            {
                "session_id": us.session_id,
                "session_name": us.session_name,
                "project_id": us.project_id,
            }
            for us in user_sessions
        ]
        return {"sessions": result}


@router.get("/project-questions/{project_id}")
def get_questions_by_project(project_id: str):
    from app.db.datasource import settings as ds_settings

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
    from app.db.datasource import settings as ds_settings

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


@router.delete("/sessions/{session_id}")
def delete_session_data(session_id: str, user_id: str = Query(None)):
    """
    Xóa một session cụ thể. Nếu có user_id, sẽ kiểm tra quyền sở hữu.
    """
    from app.db.datasource import settings as ds_settings
    from app.db.models.upload import UploadFileStatus

    engine = ds_settings._app_db_engine
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session_projects = session.exec(
            select(SessionProject).where(SessionProject.session_id == session_id)
        ).all()
        if not session_projects:
            raise HTTPException(status_code=404, detail="Session not found")

        if user_id:
            session_owner = session_projects[0].user_id
            if session_owner != user_id:
                raise HTTPException(
                    status_code=403,
                    detail="You don't have permission to delete this session",
                )

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
        # Lấy danh sách files trước khi xóa trong DB
        files_to_delete = session.exec(
            select(UploadFileStatus).where(UploadFileStatus.session_id == session_id)
        ).all()

        session.exec(
            delete(UploadFileStatus).where(UploadFileStatus.session_id == session_id)
        )
        session.commit()

        # Xóa tất cả file của session trên MinIO
        for file_record in files_to_delete:
            # Xóa file PDF
            minio_path = f"{session_id}/{file_record.file_name}"
            minio_client.delete_file(minio_path)

            # Xóa file docs (trong folder session)
            docs_path = f"{session_id}/{file_record.file_id}_docs.txt"
            minio_client.delete_file(docs_path)

        # Xóa toàn bộ folder session (bao gồm crop images và các file khác)
        all_session_files = minio_client.list_files(prefix=f"{session_id}/")
        for file_path in all_session_files:
            minio_client.delete_file(file_path)
        return {"detail": f"Deleted all data for session_id: {session_id}"}


@router.delete("/user-sessions/{user_id}")
def delete_all_user_sessions(user_id: str):
    """
    Xóa tất cả sessions của một user cụ thể
    """
    from app.db.datasource import settings as ds_settings
    from app.db.models.upload import UploadFileStatus

    engine = ds_settings._app_db_engine
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        # Lấy tất cả sessions của user
        user_sessions = session.exec(
            select(SessionProject).where(SessionProject.user_id == user_id)
        ).all()

        if not user_sessions:
            raise HTTPException(
                status_code=404, detail=f"No sessions found for user_id: {user_id}"
            )

        session_ids = [us.session_id for us in user_sessions]
        deleted_count = 0

        # Xóa từng session
        for session_id in session_ids:
            # Xóa projects và related data
            projects = session.exec(
                select(Project).where(
                    (Project.session_id == session_id) & (Project.id.is_not(None))
                )
            ).all()
            project_ids = [p.id for p in projects]

            if project_ids:
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

                session.exec(
                    delete(Question).where(Question.project_id.in_(project_ids))
                )
                session.exec(delete(Project).where(Project.session_id == session_id))

            # Lấy danh sách files trước khi xóa trong DB
            files_to_delete = session.exec(
                select(UploadFileStatus).where(
                    UploadFileStatus.session_id == session_id
                )
            ).all()

            session.exec(
                delete(UploadFileStatus).where(
                    UploadFileStatus.session_id == session_id
                )
            )

            # Xóa tất cả file của session trên MinIO
            for file_record in files_to_delete:
                # Xóa file PDF
                minio_path = f"{session_id}/{file_record.file_name}"
                minio_client.delete_file(minio_path)

                # Xóa file docs
                docs_path = f"{session_id}/{file_record.file_id}_docs.txt"
                minio_client.delete_file(docs_path)

            # Xóa toàn bộ folder session
            all_session_files = minio_client.list_files(prefix=f"{session_id}/")
            for file_path in all_session_files:
                minio_client.delete_file(file_path)

            deleted_count += 1

        # Xóa tất cả SessionProject records của user
        session.exec(delete(SessionProject).where(SessionProject.user_id == user_id))
        session.commit()

        return {
            "detail": f"Deleted {deleted_count} sessions for user_id: {user_id}",
            "deleted_sessions": session_ids,
        }


@router.get("/session-projects/{session_id}")
def get_projects_by_session(session_id: str):
    from app.db.datasource import settings as ds_settings

    engine = ds_settings._app_db_engine
    with Session(engine) as session:
        # Query trực tiếp, bỏ qua SessionProject
        projects = session.exec(
            select(Project).where(Project.session_id == session_id)
        ).all()
        return {"projects": [p.model_dump() for p in projects]}
