import os
import base64
from io import BytesIO

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pdf2image import convert_from_path
from sqlmodel import Session, select, delete

from app.schema.upload import UploadFileStatus
from app.services.datasource import insert_database
from app.config import settings as ds_settings
from app.services.vector_store import parse_pdf_text, embedding_document

router = APIRouter()
UPLOAD_DIR = "/tmp/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# nên tạo mỗi session sẽ là 1 folder để lúc xóa cả chỉ cần xóa folder đó là xong


# TODO : lưu đọc vào file
@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    file_id: str = Form(...),
):
    try:
        session_folder = os.path.join(UPLOAD_DIR, session_id)
        os.makedirs(session_folder, exist_ok=True)

        file_path = os.path.join(session_folder, file.filename)
        with open(file_path, "wb") as f:
            f.write(await file.read())

        # Lưu đường dẫn file để hiển thị ảnh
        image_path = os.path.join(session_folder, f"{file_id}_{session_id}_latest.txt")
        with open(image_path, "w") as image_file:
            image_file.write(file_path)

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
        file_name = file_record.file_name
    session_folder = os.path.join(UPLOAD_DIR, file_record.session_id)
    if active:
        # Lưu docs
        file_path = os.path.join(session_folder, file_name)
        docs = parse_pdf_text(file_path)

        docs_path = os.path.join(
            session_folder, f"{file_id}_{file_record.session_id}_docs.txt"
        )
        with open(docs_path, "w") as doc_file:
            doc_file.write(str(docs[0].page_content))

        # update vector store
        embedding_document(docs, file_record.session_id)

        return {
            "file_id": file_id,
            "active": active,
            "file_name": file_name,
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
        session_folder = os.path.join(UPLOAD_DIR, session_id)
        latest_file = os.path.join(session_folder, f"{file_id}_{session_id}_latest.txt")
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


@router.post("/upload-crop")
async def upload_cropped_image(
    file: UploadFile = File(...), session_id: str = Form(...)
):
    try:
        session_folder = os.path.join(UPLOAD_DIR, session_id)
        os.makedirs(session_folder, exist_ok=True)
        file_path = os.path.join(session_folder, file.filename)
        with open(file_path, "wb") as f:
            f.write(await file.read())

        latest_file = os.path.join(session_folder, f"{session_id}_latest_crop.txt")
        with open(latest_file, "w") as latest:
            latest.write(file_path)
    except Exception as e:
        return {"error": str(e)}


@router.delete("/delete-file/{file_id}")
async def delete_file_by_id(file_id: str):
    """
    Xóa file và các file liên quan theo file_id
    """
    try:
        engine = ds_settings._app_db_engine
        with Session(engine) as session:
            file_record = session.exec(
                select(UploadFileStatus).where(UploadFileStatus.file_id == file_id)
            ).first()
            if not file_record:
                return {"error": f"File with file_id {file_id} not found"}
            session_folder = os.path.join(UPLOAD_DIR, file_record.session_id)
            # Xóa file PDF
            file_path = os.path.join(session_folder, file_record.file_name)
            if os.path.exists(file_path):
                os.remove(file_path)
            # Xóa latest.txt
            latest_file = os.path.join(
                session_folder, f"{file_id}_{file_record.session_id}_latest.txt"
            )
            if os.path.exists(latest_file):
                os.remove(latest_file)
            # Xóa docs.txt
            docs_file = os.path.join(
                session_folder, f"{file_id}_{file_record.session_id}_docs.txt"
            )
            if os.path.exists(docs_file):
                os.remove(docs_file)
            # Xóa bản ghi trong DB
            session.exec(
                delete(UploadFileStatus).where(UploadFileStatus.file_id == file_id)
            )
            session.commit()
        return {"message": f"Deleted file and related files for file_id: {file_id}"}
    except Exception as e:
        return {"error": str(e)}
