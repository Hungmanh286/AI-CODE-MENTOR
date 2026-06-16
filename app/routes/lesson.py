import structlog

logger = structlog.get_logger(__name__)

from fastapi import APIRouter, status, Form
from app.schema.lesson import Lesson
from app.services.datasource import insert_database

router = APIRouter()


@router.post(
    "/lessons/",
    name="Create lesson",
    description="Create a new lesson with full information",
    status_code=status.HTTP_201_CREATED,
)
async def create_lesson_handler(
    lesson_name: str = Form(...),
    description: str = Form(...),
    content: str = Form(...),
    multiple_choice_exercises: str = Form("[]"),
    practice_exercises: str = Form("[]"),
):
    try:
        lesson = Lesson(
            lesson_name=lesson_name,
            description=description,
            content=content,
            multiple_choice_exercises=multiple_choice_exercises,
            practice_exercises=practice_exercises,
        )
        insert_database(lesson.model_dump(exclude_unset=True), Lesson)
        return {"message": "Lesson created successfully"}
    except Exception as e:
        logger.info(f"Error creating lesson: {e}")
        return {"error": str(e)}
