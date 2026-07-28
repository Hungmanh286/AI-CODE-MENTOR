import uuid

from fastapi import APIRouter, Form
from passlib.context import CryptContext
from sqlmodel import Session, select

from app.config import settings
from app.schema.user import User
from app.services.datasource import insert_database

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.post("/register")
async def register(
    user_name: str = Form(...),
    password: str = Form(...),
    email: str = Form(None),
    full_name: str = Form(None),
):
    try:
        # Hash password and create user
        hashed_password = pwd_context.hash(password)
        new_user = User(
            user_id=str(uuid.uuid4()),
            user_name=user_name,
            hashed_password=hashed_password,
            email=email,
            full_name=full_name,
        )
        insert_database(new_user.model_dump(exclude_unset=True), User)

        return {
            "message": "User registered successfully",
            "user_id": new_user.user_id,
            "user_name": new_user.user_name,
        }
    except Exception as e:
        return {"error": str(e)}


@router.post("/login")
async def login(
    user_name: str = Form(...),
    password: str = Form(...),
):
    try:
        engine = settings._app_db_engine
        with Session(engine) as session:
            # Find user by username
            user = session.exec(select(User).where(User.user_name == user_name)).first()

            # Verify user exists and password is correct
            if not user or not pwd_context.verify(password, user.hashed_password):
                return {"error": "Invalid username or password"}

            return {
                "message": "Login successful",
                "user_id": user.user_id,
                "user_name": user.user_name,
            }
    except Exception as e:
        return {"error": str(e)}
