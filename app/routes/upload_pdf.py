import os
import base64
from io import BytesIO

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pdf2image import convert_from_path
from sqlmodel import Session, select

from app.schema.upload import UploadFileStatus
from app.services.datasource import insert_database
from app.config import settings as ds_settings

router = APIRouter()
UPLOAD_DIR = "/tmp/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    file_id: str = Form(...),
):
    try:
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as f:
            f.write(await file.read())

        # Lưu đường dẫn file mới nhất theo user/session
        latest_file = os.path.join(UPLOAD_DIR, f"{file_id}_{session_id}_latest.txt")
        with open(latest_file, "w") as latest:
            latest.write(file_path)

        # Lưu thông tin file vào bảng UploadFileStatus
        file_status_data = {
            "file_id": file_id,
            "session_id": session_id,
            "file_name": file.filename,
            "active": False,
        }
        insert_database(file_status_data, UploadFileStatus)

        return {"file_path": file_path, "message": "File uploaded successfully."}
    except Exception as e:
        return {"error": str(e)}


@router.put("/update-file-active")
async def update_file_active(file_id: str = Form(...), active: bool = Form(...)):
    """
    Cập nhật trạng thái active của file theo file_id
    """
    engine = ds_settings._app_db_engine
    with Session(engine) as session:
        file_record = session.exec(
            select(UploadFileStatus).where(UploadFileStatus.file_id == file_id)
        ).first()
        if not file_record:
            return {"error": f"File with file_id {file_id} not found"}
        file_record.active = active
        session.add(file_record)
        session.commit()
        return {
            "file_id": file_id,
            "active": active,
            "message": "File status updated successfully.",
        }


@router.get("/session-files/{session_id}")
async def get_files_by_session(session_id: str):
    """
    Lấy tất cả file_id thuộc về session_id
    """
    try:
        engine = ds_settings._app_db_engine
        with Session(engine) as session:
            files = session.exec(
                select(UploadFileStatus.file_id).where(
                    UploadFileStatus.session_id == session_id
                )
            ).all()
            return files
    except Exception as e:
        print(f"Error retrieving files for session_id {session_id}: {e}")
        return


@router.get("/view-file")
async def view_file(session_id: str, file_id: str):
    try:
        latest_file = os.path.join(UPLOAD_DIR, f"{file_id}_{session_id}_latest.txt")
        if not os.path.exists(latest_file):
            return {"error": "File not found."}
        with open(latest_file, "r", encoding="utf-8") as f:
            pdf_path = f.read().strip()
        if not os.path.exists(pdf_path):
            return {"error": "PDF file not found."}
        # Chuyển PDF sang ảnh (lấy tất cả các trang)
        images = convert_from_path(pdf_path)
        if not images:
            return {"error": "No image generated from PDF."}
        img_base64_list = []
        for img in images:
            img_byte_arr = BytesIO()
            img.save(img_byte_arr, format="PNG")
            img_byte_arr = img_byte_arr.getvalue()
            img_base64 = base64.b64encode(img_byte_arr).decode("utf-8")
            img_base64_list.append(img_base64)
        return JSONResponse({"images_base64": img_base64_list})
    except Exception as e:
        return {"error": str(e)}
