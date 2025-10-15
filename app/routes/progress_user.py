from fastapi import APIRouter, status, Form
from app.schema.user import ProgressUser
from app.services.datasource import insert_database

router = APIRouter()


@router.post(
    "/progress/",
    name="Create progress",
    description="Create a new user progress for a lesson",
    status_code=status.HTTP_201_CREATED,
)
async def create_progress_handler(
    lesson_id: str = Form(...),
    user_id: str = Form(...),
    lesson_name: str = Form(...),
    user_name: str = Form(...),
    progress: str = Form(...),
):
    try:
        progress_user = ProgressUser(
            lesson_id=lesson_id,
            user_id=user_id,
            lesson_name=lesson_name,
            user_name=user_name,
            progress=progress,
        )
        insert_database(progress_user.model_dump(exclude_unset=True), ProgressUser)
        return {"message": "Progress created successfully"}
    except Exception as e:
        print(f"Error creating progress: {e}")
        return {"error": str(e)}
