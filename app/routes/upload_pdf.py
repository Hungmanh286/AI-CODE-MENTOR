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
from app.services.vector_store import parse_pdf_text2, embedding_document
from app.services.minio_client import minio_client

router = APIRouter()


# TODO : lưu đọc vào file
@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    file_id: str = Form(...),
):
    try:
        file_path = f"{session_id}/{file.filename}"
        temp_local_path = f"/tmp/{file.filename}"

        # Ghi file tạm
        with open(temp_local_path, "wb") as f:
            f.write(await file.read())

        # Upload lên MinIO
        minio_client.upload_file(temp_local_path, file_path)
        os.remove(temp_local_path)

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
    Cập nhật trạng thái active của file theo file_id. Chỉ thực hiện lưu docs và update vector store khi active chuyển từ False sang True lần đầu tiên (has_processed=False).
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
        minio_path = f"{file_record.session_id}/{file_name}"

        # Download file từ MinIO về tạm để xử lý
        temp_local_path = f"/tmp/{file_name}"
        minio_client.download_file(minio_path, temp_local_path)

        if file_record.active and not file_record.has_processed:
            file_record.has_processed = True
            docs = parse_pdf_text2(temp_local_path)

            # Upload docs lên MinIO trong folder session
            docs_minio_path = f"{file_record.session_id}/{file_id}_docs.txt"
            temp_docs_path = f"/tmp/{file_id}_docs.txt"
            with open(temp_docs_path, "w", encoding="utf-8") as doc_file:
                doc_file.write(str(docs))

            minio_client.upload_file(temp_docs_path, docs_minio_path)
            embedding_document([docs], file_record.session_id)

            os.remove(temp_docs_path)
            session.add(file_record)
            session.commit()

        os.remove(temp_local_path)

        # Lấy giá trị has_processed TRONG session trước khi session đóng
        has_processed = file_record.has_processed

    return {
        "file_id": file_id,
        "active": active,
        "file_name": file_name,
        "has_processed": has_processed,
        "message": "File status updated successfully.",
    }


@router.get("/session-files/{session_id}")
async def get_files_by_session(session_id: str):
    """
    Lấy tất cả file_id và file_name thuộc về session_id
    """
    try:
        engine = ds_settings._app_db_engine
        with Session(engine) as session:
            files = session.exec(
                select(UploadFileStatus).where(
                    UploadFileStatus.session_id == session_id
                )
            ).all()
            result = [{"file_id": f.file_id, "file_name": f.file_name} for f in files]
            return result
    except Exception as e:
        print(f"Error retrieving files for session_id {session_id}: {e}")
        return []


@router.get("/view-file")
async def view_file(session_id: str, file_id: str):
    try:
        # Lấy thông tin file từ database
        engine = ds_settings._app_db_engine
        with Session(engine) as session:
            file_record = session.exec(
                select(UploadFileStatus).where(UploadFileStatus.file_id == file_id)
            ).first()
            if not file_record:
                return {"error": "File not found in database."}

            file_name = file_record.file_name
            minio_path = f"{session_id}/{file_name}"

            # Download file từ MinIO về tạm
            temp_local_path = f"/tmp/view_{file_name}"
            if not minio_client.download_file(minio_path, temp_local_path):
                return {"error": "PDF file not found in MinIO."}

            # Chuyển PDF sang ảnh (lấy tất cả các trang)
            images = convert_from_path(temp_local_path)
            if not images:
                os.remove(temp_local_path)
                return {"error": "No image generated from PDF."}

            img_base64_list = []
            for img in images:
                img_byte_arr = BytesIO()
                img.save(img_byte_arr, format="PNG")
                img_byte_arr = img_byte_arr.getvalue()
                img_base64 = base64.b64encode(img_byte_arr).decode("utf-8")
                img_base64_list.append(img_base64)

            # Xóa file tạm
            os.remove(temp_local_path)

            return JSONResponse({"images_base64": img_base64_list})
    except Exception as e:
        return {"error": str(e)}


@router.post("/upload-crop")
async def upload_cropped_image(
    file: UploadFile = File(...), file_id: str = Form(...), session_id: str = Form(...)
):
    try:
        # Upload ảnh crop lên MinIO
        crop_minio_path = f"{session_id}/crop_{file_id}_{file.filename}"
        temp_local_path = f"/tmp/crop_{file.filename}"

        # Ghi file tạm
        with open(temp_local_path, "wb") as f:
            f.write(await file.read())

        # Upload lên MinIO
        minio_client.upload_file(temp_local_path, crop_minio_path)
        os.remove(temp_local_path)

        return {
            "message": "Cropped image uploaded successfully.",
            "path": crop_minio_path,
        }
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

            # Xóa file PDF trên MinIO
            minio_path = f"{file_record.session_id}/{file_record.file_name}"
            minio_client.delete_file(minio_path)

            # Xóa docs.txt trên MinIO (trong folder session)
            docs_minio_path = f"{file_record.session_id}/{file_id}_docs.txt"
            minio_client.delete_file(docs_minio_path)

            # Xóa ảnh crop nếu có
            crop_files = minio_client.list_files(
                prefix=f"{file_record.session_id}/crop_{file_id}"
            )
            for crop_file in crop_files:
                minio_client.delete_file(crop_file)

            # Xóa bản ghi trong DB
            session.exec(
                delete(UploadFileStatus).where(UploadFileStatus.file_id == file_id)
            )
            session.commit()

        return {"message": f"Deleted file and related files for file_id: {file_id}"}
    except Exception as e:
        return {"error": str(e)}
