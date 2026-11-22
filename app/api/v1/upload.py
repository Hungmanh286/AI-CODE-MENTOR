import base64
import os
import tempfile
import time
import uuid
from io import BytesIO

import structlog
from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse
from pdf2image import convert_from_path
from sqlmodel import Session, delete, select

from app.core.config import settings as ds_settings
from app.db.datasource import insert_database
from app.db.models.upload import UploadFileStatus
from app.infra.minio_client import minio_client
from app.infra.vector_store import PdfParseError, embedding_document, parse_pdf_parallel
from app.services.agui_documents import clean_document_text

logger = structlog.get_logger(__name__)

router = APIRouter()

TMP_DIR = tempfile.gettempdir()


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
def update_file_active(file_id: str = Form(...), active: bool = Form(...)):
    """
    Cập nhật trạng thái active của file theo file_id. Khi file được bật mà chưa có nội dung
    (chưa xử lý, hoặc lần xử lý trước lỗi) thì parse PDF, lưu docs và cập nhật vector store.

    Hàm đồng bộ (``def``) có chủ ý: FastAPI chạy nó trong threadpool, nên việc parse
    (hàng chục giây) không chặn event loop và các request khác.
    """
    engine = ds_settings._app_db_engine
    error = None
    with Session(engine) as session:
        file_record = session.exec(
            select(UploadFileStatus).where(UploadFileStatus.file_id == file_id)
        ).first()
        if not file_record:
            return {"error": f"File with file_id {file_id} not found"}

        file_record.active = active
        session.add(file_record)
        session.commit()

        if active and (not file_record.has_processed or not _has_document_text(file_record)):
            error = _process_file(file_record)
            file_record.has_processed = error is None
            session.add(file_record)
            session.commit()

        file_name = file_record.file_name
        has_processed = file_record.has_processed

    response = {
        "file_id": file_id,
        "active": active,
        "file_name": file_name,
        "has_processed": has_processed,
        "message": "File status updated successfully.",
    }
    if error:
        response["error"] = error
    return response


PARSE_FAILED_MESSAGE = (
    "Không xử lý được tài liệu (lỗi khi đọc PDF). Bạn hãy tắt rồi bật lại tài liệu để thử lại."
)


def _docs_path(file_record: UploadFileStatus) -> str:
    return f"{file_record.session_id}/{file_record.file_id}_docs.txt"


def _has_document_text(file_record: UploadFileStatus) -> bool:
    """False when the stored text is missing or only parse-error markers (files
    marked processed before a failed parse was reported as a failure)."""
    path = _docs_path(file_record)
    data = minio_client.download_data(path) if minio_client.file_exists(path) else None
    return bool(data) and bool(clean_document_text(data.decode("utf-8", errors="replace")))


def _process_file(file_record: UploadFileStatus) -> str | None:
    """Parse the PDF, store its text and embed it. Returns an error message or None."""
    file_id = file_record.file_id
    stem = os.path.join(TMP_DIR, f"{file_id}-{uuid.uuid4().hex}")
    pdf_path, docs_path = f"{stem}.pdf", f"{stem}_docs.txt"
    try:
        minio_client.download_file(f"{file_record.session_id}/{file_record.file_name}", pdf_path)
        logger.info(f"🚀 Starting parallel PDF processing for file_id: {file_id}")
        start_time = time.time()
        docs = parse_pdf_parallel(file_path=pdf_path, max_workers=ds_settings.PDF_PARSE_MAX_WORKERS)
        if not docs.strip():
            raise PdfParseError("the PDF produced no text")
        parsing_time = time.time() - start_time
        logger.info(f"✅ Parsed {len(docs):,} characters in {parsing_time:.2f}s")

        with open(docs_path, "w", encoding="utf-8") as doc_file:
            doc_file.write(docs)
        minio_client.upload_file(docs_path, _docs_path(file_record))

        embedding_document(
            [docs], file_record.session_id, file_id=file_id, file_name=file_record.file_name
        )
        logger.info(f"🎉 File {file_id} processed in {time.time() - start_time:.2f}s")
        return None
    except Exception as exc:  # the client gets a generic message; details stay in the log
        logger.warning(f"processing file {file_id} failed: {exc!r}")
        return PARSE_FAILED_MESSAGE
    finally:
        for path in (pdf_path, docs_path):
            if os.path.exists(path):
                os.remove(path)


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
        logger.info(f"Error retrieving files for session_id {session_id}: {e}")
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
        crop_minio_path = f"{session_id}/crop_{file_id}_{file.filename}"
        temp_local_path = f"/tmp/crop_{file.filename}"

        with open(temp_local_path, "wb") as f:
            f.write(await file.read())

        minio_client.upload_file(temp_local_path, crop_minio_path)
        os.remove(temp_local_path)

        return {
            "message": "Cropped image uploaded successfully.",
            "path": crop_minio_path,
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/get-mindmap")
async def get_mindmap(session_id: str):
    """
    Lấy ảnh mind map từ MinIO theo session_id
    Trả về base64 encoded image
    """
    try:
        mindmap_path = f"{session_id}/mindmap.png"

        if not minio_client.file_exists(mindmap_path):
            return {"error": "Mind map not found for this session."}

        image_data = minio_client.download_data(mindmap_path)
        if not image_data:
            return {"error": "Failed to download mind map from MinIO."}

        img_base64 = base64.b64encode(image_data).decode("utf-8")

        return JSONResponse(
            {"session_id": session_id, "image_base64": img_base64, "path": mindmap_path}
        )

    except Exception as e:
        return {"error": str(e)}


@router.get("/get-mindmap-url")
async def get_mindmap_url(session_id: str, expiry: int = 3600):
    """
    Lấy presigned URL của mind map từ MinIO

    Args:
        session_id: ID của session
        expiry: Thời gian URL hợp lệ (giây), mặc định 1 giờ

    Returns:
        URL tạm thời để download/view mind map
    """
    try:
        mindmap_path = f"{session_id}/mindmap.png"

        # Check if file exists
        if not minio_client.file_exists(mindmap_path):
            return {"error": "Mind map not found for this session."}

        # Get presigned URL
        url = minio_client.get_presigned_url(mindmap_path, expiry_seconds=expiry)

        return JSONResponse(
            {
                "session_id": session_id,
                "url": url,
                "expiry_seconds": expiry,
                "path": mindmap_path,
            }
        )

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
            minio_path = f"{file_record.session_id}/{file_record.file_name}"
            minio_client.delete_file(minio_path)
            docs_minio_path = f"{file_record.session_id}/{file_id}_docs.txt"
            minio_client.delete_file(docs_minio_path)
            crop_files = minio_client.list_files(
                prefix=f"{file_record.session_id}/crop_{file_id}"
            )
            for crop_file in crop_files:
                minio_client.delete_file(crop_file)
            session.exec(
                delete(UploadFileStatus).where(UploadFileStatus.file_id == file_id)
            )
            session.commit()

        return {"message": f"Deleted file and related files for file_id: {file_id}"}
    except Exception as e:
        return {"error": str(e)}
