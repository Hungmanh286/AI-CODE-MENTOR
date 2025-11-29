import json
import uuid

from fastapi import APIRouter, Form, HTTPException, Query
from sqlmodel import SQLModel, Session, select, delete
from langfuse.callback import CallbackHandler
from langchain_core.runnables.config import RunnableConfig

from app.schema.question import Project, Question, QuestionOption, SessionProject
from app.services.datasource import insert_database
from app.services.datasource import get_active_file_id
from app.services.minio_client import minio_client
from app.config import settings

router = APIRouter()

tracer = CallbackHandler(
    tags=["code"],
    public_key=settings.LANGFUSE_PUBLIC_KEY,
    secret_key=settings.LANGFUSE_SECRET_KEY,
    host=settings.LANGFUSE_HOST,
)


async def process_pdf(session_id: str, query: str, document_processing_agent=None):
    # Gọi question_expert để xử lý PDF và sinh câu hỏi
    config = RunnableConfig(configurable={"thread_id": session_id}, callbacks=[tracer])
    result = await document_processing_agent.ainvoke({"query": query}, config)
    evaluated_result = result["quizz"]
    questions_data = json.loads(evaluated_result)

    # Lấy thông tin file từ database
    file_ids = get_active_file_id(session_id)
    file_id = file_ids[0] if file_ids else None

    # Lấy tên file từ database thay vì từ local file
    from app.schema.upload import UploadFileStatus

    engine = settings._app_db_engine
    with Session(engine) as session:
        file_record = session.exec(
            select(UploadFileStatus).where(UploadFileStatus.file_id == file_id)
        ).first()
        file_name = file_record.file_name if file_record else "unknown.pdf"

    # Tạo project mới
    project_id = str(uuid.uuid4())

    project_data = {
        "id": project_id,
        "session_id": session_id,
        "name": file_name,
        "source_path": f"{session_id}/{file_name}",
    }

    insert_database(project_data, Project)

    from app.schema.question import SessionProject

    session_project_data = {"session_id": session_id, "project_id": project_id}
    try:
        insert_database(session_project_data, SessionProject)
    except Exception as e:
        pass
        print(f"Error inserting session project: {e}")

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
def create_session(
    session_id: str = Form(...),
    user_id: str = Form(...),
    project_id: str = Form(None),
    session_name: str = Form(...),
):
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


@router.get("/user-sessions/{user_id}")
def get_sessions_by_user(user_id: str):
    """
    Lấy tất cả sessions của một user cụ thể
    """
    from app.services.datasource import settings as ds_settings

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


@router.delete("/sessions/{session_id}")
def delete_session_data(session_id: str, user_id: str = Query(None)):
    """
    Xóa một session cụ thể. Nếu có user_id, sẽ kiểm tra quyền sở hữu.
    """
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

        # Kiểm tra quyền sở hữu nếu có user_id
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
    from app.services.datasource import settings as ds_settings
    from app.schema.upload import UploadFileStatus

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
    from app.services.datasource import settings as ds_settings

    engine = ds_settings._app_db_engine
    with Session(engine) as session:
        # Query trực tiếp, bỏ qua SessionProject
        projects = session.exec(
            select(Project).where(Project.session_id == session_id)
        ).all()
        return {"projects": [p.dict() for p in projects]}
