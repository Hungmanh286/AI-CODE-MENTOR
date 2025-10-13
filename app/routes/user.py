from fastapi import APIRouter, HTTPException
from app.schema.user import User
from app.services.datasource import insert_database, update_database
from sqlmodel import Session, select
from app.config import settings

router = APIRouter()


@router.post("/users/", response_model=User)
def create_user(user: User):
    insert_database(user.model_dump(exclude_unset=True), User)
    return user


@router.put("/users/{user_id}", response_model=User)
def update_user(user_id: int, user: User):
    data = user.model_dump(exclude_unset=True)
    data["id"] = user_id
    update_database(data, User)
    return user


@router.delete("/users/{user_id}")
def delete_user(user_id: int):
    with Session(settings._app_db_engine) as session:
        statement = select(User).where(User.id == user_id)
        result = session.exec(statement).first()
        if not result:
            raise HTTPException(status_code=404, detail="User not found")
        session.delete(result)
        session.commit()
    return {"ok": True}
