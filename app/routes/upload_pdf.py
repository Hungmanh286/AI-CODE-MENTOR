import os
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pdf2image import convert_from_path
import base64
from io import BytesIO

router = APIRouter()
UPLOAD_DIR = "/tmp/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    session_id: str = Form(...),
):
    try:
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as f:
            f.write(await file.read())

        # Lưu đường dẫn file mới nhất theo user/session
        latest_file = os.path.join(UPLOAD_DIR, f"{session_id}_latest.txt")
        with open(latest_file, "w") as latest:
            latest.write(file_path)
        return {"file_path": file_path, "message": "File uploaded successfully."}
    except Exception as e:
        return {"error": str(e)}


@router.get("/view-file")
async def view_file(session_id: str):
    try:
        latest_file = os.path.join(UPLOAD_DIR, f"{session_id}_latest.txt")
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
