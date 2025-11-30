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
from app.services.vector_store import embedding_document
from app.services.vector_store_parallel import parse_pdf_parallel
# from app.config.parallel_processing import Presets
from app.services.minio_client import minio_client
"""
Cấu hình cho parallel processing.
Điều chỉnh các giá trị này tùy theo plan API và hardware của bạn.
"""

from dataclasses import dataclass
from typing import Literal


@dataclass
class ParallelProcessingConfig:
    """Cấu hình chung cho parallel processing"""
    
    # ========== Threading Configuration ==========
    MAX_WORKERS: int = 10
    """Số lượng worker threads tối đa (10 workers phù hợp với 15 RPM)"""
    
    # ========== Rate Limiting Configuration ==========
    # Tham khảo: https://ai.google.dev/pricing
    RPM_LIMIT: int = 15
    """
    Requests Per Minute limit
    - Gemini Free tier: 15 RPM
    - Gemini Pro (paid): 360 RPM
    - OpenAI GPT-4: 500 RPM (tùy plan)
    """
    
    RPD_LIMIT: int = 1500
    """
    Requests Per Day limit
    - Gemini Free tier: 1500 RPD
    - Gemini Pro (paid): không giới hạn
    """
    
    # ========== Chunking Configuration ==========
    CHUNK_SIZE_SMALL: int = 15
    """Số trang/chunk cho PDF nhỏ (<50 trang)"""
    
    CHUNK_SIZE_LARGE: int = 30
    """Số trang/chunk cho PDF lớn (>=50 trang)"""
    
    CHUNK_SIZE_THRESHOLD: int = 50
    """Ngưỡng phân biệt PDF nhỏ/lớn"""
    
    # ========== Retry Configuration ==========
    RETRY_ATTEMPTS: int = 3
    """Số lần retry khi chunk parsing fail"""
    
    RETRY_DELAY: int = 2
    """Delay (seconds) giữa các retry"""
    
    RETRY_BACKOFF_MULTIPLIER: float = 2.0
    """Multiplier cho exponential backoff (2^n delay)"""
    
    # ========== Timeout Configuration ==========
    API_TIMEOUT: int = 60
    """Timeout (seconds) cho mỗi API call"""
    
    TOTAL_TIMEOUT: int = 3600
    """Timeout (seconds) cho toàn bộ quá trình parsing (1 giờ)"""
    
    # ========== Memory Configuration ==========
    MAX_CONCURRENT_CHUNKS_IN_MEMORY: int = 50
    """
    Số chunks tối đa được load vào memory cùng lúc
    Mỗi chunk ~5-10MB → 50 chunks = 250-500MB
    """
    
    ENABLE_MEMORY_OPTIMIZATION: bool = True
    """
    Bật tối ưu hóa memory (giải phóng chunks sau khi xử lý xong)
    """
    
    # ========== API Selection ==========
    DEFAULT_API: Literal["gemini", "openai"] = "gemini"
    """API mặc định để sử dụng"""
    
    FALLBACK_API: Literal["gemini", "openai", None] = "openai"
    """
    API dự phòng khi API chính fail
    Set None để disable fallback
    """
    
    # ========== Logging Configuration ==========
    ENABLE_VERBOSE_LOGGING: bool = True
    """Bật logging chi tiết"""
    
    LOG_FILE: str = "parallel_processing.log"
    """Đường dẫn file log"""
    
    ENABLE_PROGRESS_BAR: bool = True
    """Hiển thị progress bar với tqdm"""
    
    # ========== Output Configuration ==========
    SAVE_INTERMEDIATE_RESULTS: bool = False
    """
    Lưu kết quả từng chunk vào file riêng
    Hữu ích khi debug hoặc xử lý dataset rất lớn
    """
    
    INTERMEDIATE_OUTPUT_DIR: str = "./temp_chunks"
    """Thư mục lưu kết quả tạm thời của từng chunk"""
    
    # ========== Performance Optimization ==========
    ENABLE_CACHING: bool = True
    """
    Cache kết quả parsing để tránh xử lý lại chunks đã parse
    """
    
    CACHE_DIR: str = "./.cache/parsed_chunks"
    """Thư mục lưu cache"""
    
    CACHE_EXPIRY_DAYS: int = 7
    """Thời gian cache hết hạn (days)"""


@dataclass
class GeminiConfig:
    """Cấu hình riêng cho Gemini API"""
    
    MODEL_NAME: str = "gemini-2.0-flash-exp"
    """
    Gemini models:
    - gemini-2.0-flash-exp: Nhanh nhất, free 15 RPM
    - gemini-2.5-pro-exp-03-25: Chất lượng cao hơn
    - gemini-1.5-flash: Stable version
    """
    
    TEMPERATURE: float = 0.1
    """Temperature cho generation (0.0 = deterministic, 1.0 = creative)"""
    
    MAX_OUTPUT_TOKENS: int = 8192
    """Số tokens tối đa trong output"""
    
    SAFETY_SETTINGS: dict = None
    """Safety settings cho content filtering"""
    
    def __post_init__(self):
        if self.SAFETY_SETTINGS is None:
            from google.genai import types
            self.SAFETY_SETTINGS = {
                types.HarmCategory.HARM_CATEGORY_HATE_SPEECH: types.HarmBlockThreshold.BLOCK_NONE,
                types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: types.HarmBlockThreshold.BLOCK_NONE,
                types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: types.HarmBlockThreshold.BLOCK_NONE,
                types.HarmCategory.HARM_CATEGORY_HARASSMENT: types.HarmBlockThreshold.BLOCK_NONE,
            }


@dataclass
class OpenAIConfig:
    """Cấu hình riêng cho OpenAI API"""
    
    MODEL_NAME: str = "gpt-4o-mini"
    """
    OpenAI models:
    - gpt-4o-mini: Rẻ, nhanh
    - gpt-4o: Chất lượng cao
    - gpt-4-turbo: Balance giữa speed và quality
    """
    
    TEMPERATURE: float = 0.1
    """Temperature cho generation"""
    
    MAX_TOKENS: int = 4096
    """Số tokens tối đa trong response"""
    
    TOP_P: float = 1.0
    """Nucleus sampling parameter"""


# ========== Presets ==========

class Presets:
    """Các preset cấu hình cho different use cases"""
    
    @staticmethod
    def free_tier():
        """Cấu hình tối ưu cho Free Tier (Gemini 15 RPM)"""
        return ParallelProcessingConfig(
            MAX_WORKERS=3,  # Thấp để tránh hit rate limit
            RPM_LIMIT=15,
            RPD_LIMIT=1500,
            CHUNK_SIZE_SMALL=15,
            CHUNK_SIZE_LARGE=30,
            RETRY_ATTEMPTS=3,
            DEFAULT_API="gemini",
            FALLBACK_API=None,
        )
    
    @staticmethod
    def paid_tier():
        """Cấu hình cho Paid Tier (Gemini Pro/OpenAI)"""
        return ParallelProcessingConfig(
            MAX_WORKERS=20,
            RPM_LIMIT=360,  # Gemini Pro
            RPD_LIMIT=None,
            CHUNK_SIZE_SMALL=10,
            CHUNK_SIZE_LARGE=20,
            RETRY_ATTEMPTS=2,
            DEFAULT_API="gemini",
            FALLBACK_API="openai",
        )
    
    @staticmethod
    def high_performance():
        """Cấu hình tối ưu performance (yêu cầu paid tier)"""
        return ParallelProcessingConfig(
            MAX_WORKERS=30,
            RPM_LIMIT=500,
            CHUNK_SIZE_SMALL=8,
            CHUNK_SIZE_LARGE=15,
            RETRY_ATTEMPTS=2,
            ENABLE_CACHING=True,
            ENABLE_MEMORY_OPTIMIZATION=True,
            DEFAULT_API="openai",  # OpenAI thường nhanh hơn
        )
    
    @staticmethod
    def cost_optimized():
        """Cấu hình tối ưu chi phí (chunks lớn hơn, ít requests)"""
        return ParallelProcessingConfig(
            MAX_WORKERS=5,
            RPM_LIMIT=15,
            CHUNK_SIZE_SMALL=30,
            CHUNK_SIZE_LARGE=50,
            RETRY_ATTEMPTS=3,
            ENABLE_CACHING=True,
            DEFAULT_API="gemini",  # Gemini free/cheaper
        )
    
    @staticmethod
    def development():
        """Cấu hình cho development/testing"""
        return ParallelProcessingConfig(
            MAX_WORKERS=2,
            RPM_LIMIT=15,
            CHUNK_SIZE_SMALL=5,
            CHUNK_SIZE_LARGE=10,
            RETRY_ATTEMPTS=1,
            ENABLE_VERBOSE_LOGGING=True,
            SAVE_INTERMEDIATE_RESULTS=True,
            DEFAULT_API="gemini",
        )


# Apply parallel processing config (Free Tier by default)
# Có thể thay đổi thành paid_tier() hoặc high_performance() nếu cần
PARALLEL_CONFIG = Presets.free_tier()

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
            import time
            print(f"🚀 Starting parallel PDF processing for file_id: {file_id}")
            print(f"⚙️  Config: {PARALLEL_CONFIG.MAX_WORKERS} workers, {PARALLEL_CONFIG.RPM_LIMIT} RPM limit")
            
            start_time = time.time()
            file_record.has_processed = True
            
            # Sử dụng parallel processing thay vì sequential
            # use_gemini=False → dùng OpenAI (parse_chunk format)
            # use_gemini=True → dùng Gemini (parse_chunk_2 format)
            docs = parse_pdf_parallel(
                file_path=temp_local_path,
                use_gemini=False,  # Dùng OpenAI với format đúng như parse_chunk()
                max_workers=PARALLEL_CONFIG.MAX_WORKERS
            )
            
            processing_time = time.time() - start_time
            print(f"✅ Parallel processing completed in {processing_time:.2f}s")
            print(f"📄 Processed {len(docs):,} characters")

            # Upload docs lên MinIO trong folder session
            docs_minio_path = f"{file_record.session_id}/{file_id}_docs.txt"
            temp_docs_path = f"/tmp/{file_id}_docs.txt"
            with open(temp_docs_path, "w", encoding="utf-8") as doc_file:
                doc_file.write(str(docs))

            minio_client.upload_file(temp_docs_path, docs_minio_path)
            
            print(f"🔍 Starting embedding to vector store...")
            embedding_start = time.time()
            embedding_document([docs], file_record.session_id)
            embedding_time = time.time() - embedding_start
            print(f"✅ Embedding completed in {embedding_time:.2f}s")

            os.remove(temp_docs_path)
            session.add(file_record)
            session.commit()
            
            total_time = time.time() - start_time
            print(f"🎉 Total processing time: {total_time:.2f}s (parsing: {processing_time:.2f}s, embedding: {embedding_time:.2f}s)")

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
