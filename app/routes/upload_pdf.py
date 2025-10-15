import os
from fastapi import APIRouter, UploadFile, File, Form

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
