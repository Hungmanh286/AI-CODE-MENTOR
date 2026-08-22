"""Quiz persistence: run the document-processing agent and store its questions."""

import json
import uuid

import structlog
from langchain_core.runnables.config import RunnableConfig
from langfuse.langchain import CallbackHandler
from sqlmodel import Session, select

from app.core.config import settings
from app.db.datasource import get_active_file_id, insert_database
from app.db.models.question import Project, Question, QuestionOption, SessionProject
from app.db.models.upload import UploadFileStatus

logger = structlog.get_logger(__name__)

tracer = CallbackHandler()


async def process_pdf(session_id: str, query: str, document_processing_agent=None):
    # Gọi question_expert để xử lý PDF và sinh câu hỏi
    config = RunnableConfig(
        configurable={"thread_id": session_id, "query": query}, callbacks=[tracer]
    )
    result = await document_processing_agent.ainvoke({"query": query}, config)
    evaluated_result = result["quizz"]
    questions_data = json.loads(evaluated_result)

    file_ids = get_active_file_id(session_id)
    file_id = file_ids[0] if file_ids else None

    engine = settings._app_db_engine
    with Session(engine) as session:
        file_record = session.exec(
            select(UploadFileStatus).where(UploadFileStatus.file_id == file_id)
        ).first()
        file_name = file_record.file_name if file_record else "unknown.pdf"

    project_id = str(uuid.uuid4())

    project_data = {
        "id": project_id,
        "session_id": session_id,
        "name": file_name,
        "source_path": f"{session_id}/{file_name}",
    }

    insert_database(project_data, Project)

    session_project_data = {"session_id": session_id, "project_id": project_id}
    try:
        insert_database(session_project_data, SessionProject)
    except Exception as e:
        pass
        logger.info(f"Error inserting session project: {e}")

    for q in questions_data:
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

        insert_database(question_data, Question)

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
