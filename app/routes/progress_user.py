from fastapi import APIRouter, HTTPException
from app.schema.user import ProgressUser
from app.services.datasource import insert_database, update_database
from sqlmodel import Session, select
from app.config import settings

router = APIRouter()


@router.post("/progress/", response_model=ProgressUser)
def create_progress(progress: ProgressUser):
    insert_database(progress.model_dump(exclude_unset=True), ProgressUser)
    return progress


@router.put("/progress/{progress_id}", response_model=ProgressUser)
def update_progress(progress_id: int, progress: ProgressUser):
    data = progress.model_dump(exclude_unset=True)
    data["id"] = progress_id
    update_database(data, ProgressUser)
    return progress


@router.delete("/progress/{progress_id}")
def delete_progress(progress_id: int):
    with Session(settings._app_db_engine) as session:
        statement = select(ProgressUser).where(ProgressUser.id == progress_id)
        result = session.exec(statement).first()
        if not result:
            raise HTTPException(status_code=404, detail="Progress not found")
        session.delete(result)
        session.commit()
    return {"ok": True}
