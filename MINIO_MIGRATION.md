# Migration từ Local Storage sang MinIO

## Tổng quan

Đã hoàn tất việc migrate từ lưu trữ file local sang MinIO Object Storage. Tất cả các file PDF, docs, và ảnh crop giờ đây được lưu trữ trên MinIO thay vì local filesystem.

## Thay đổi chính

### 1. MinIO Service (`app/services/minio_client.py`)

Tạo MinIO client service với các chức năng:
- `upload_file()`: Upload file lên MinIO
- `upload_data()`: Upload dữ liệu bytes lên MinIO
- `download_file()`: Download file từ MinIO về local tạm thời
- `download_data()`: Download dữ liệu bytes từ MinIO
- `delete_file()`: Xóa file trên MinIO
- `file_exists()`: Kiểm tra file có tồn tại không
- `list_files()`: Liệt kê các file theo prefix

**Singleton instance**: `minio_client` để sử dụng trong toàn bộ app

### 2. Config (`app/config.py`)

Thêm các cấu hình MinIO:
```python
MINIO_ENDPOINT: str = "localhost:9000"
MINIO_ACCESS_KEY: str = "admin"
MINIO_SECRET_KEY: str = "admin123"
MINIO_SECURE: bool = False
MINIO_BUCKET: str = "mybucket"
```

Có thể override qua biến môi trường trong `.env`:
```env
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=admin
MINIO_SECRET_KEY=admin123
MINIO_SECURE=false
MINIO_BUCKET=mybucket
```

### 3. Files đã cập nhật

#### Routes
- **`app/routes/upload_pdf.py`**:
  - `/upload`: Upload PDF lên MinIO
  - `/update-file-active`: Download PDF từ MinIO, xử lý, upload docs lên MinIO
  - `/view-file`: Download PDF từ MinIO để hiển thị
  - `/upload-crop`: Upload ảnh crop lên MinIO
  - `/delete-file/{file_id}`: Xóa tất cả file liên quan trên MinIO

- **`app/routes/process_data.py`**:
  - Đọc thông tin file từ database thay vì local file
  - Xóa tất cả file trên MinIO khi xóa session

#### Agents
- **`app/graph/agents/document_processing.py`**: Đọc docs từ MinIO
- **`app/graph/agents/question_expert.py`**: Đọc docs từ MinIO
- **`app/graph/agents/summarize_agent.py`**: Đọc docs từ MinIO
- **`app/graph/agents/feedbacks_answer.py`**: Đọc ảnh crop từ MinIO

#### Tools
- **`app/graph/tools/retrieval_tool.py`**: Download PDF từ MinIO để xử lý

### 4. Cấu trúc lưu trữ trên MinIO

```
mybucket/
└── {session_id}/                         # Mỗi session có 1 folder riêng
    ├── {filename}.pdf                    # File PDF gốc
    ├── {file_id}_docs.txt                # Nội dung đã parse từ PDF
    └── crop_{file_id}_{filename}         # Ảnh crop (nếu có)
```

**Lưu ý**: Tất cả file liên quan đến một session đều nằm trong cùng folder `{session_id}/` để dễ quản lý và xóa.

## Cách sử dụng

### 1. Setup MinIO Server

Cài đặt và chạy MinIO:

```bash
# Docker
docker run -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=admin \
  -e MINIO_ROOT_PASSWORD=admin123 \
  minio/minio server /data --console-address ":9001"
```

Hoặc download binary:
```bash
wget https://dl.min.io/server/minio/release/linux-amd64/minio
chmod +x minio
./minio server /data --console-address ":9001"
```

Access MinIO Console: http://localhost:9001
- Username: `admin`
- Password: `admin123`

### 2. Tạo Bucket

Tạo bucket `mybucket` qua MinIO Console hoặc tự động tạo khi khởi động app (đã có trong code).

### 3. Chạy Application

```bash
# Cài đặt dependencies
pip install minio

# Chạy app
python main.py
```

## API Flow

### Upload & Process PDF

1. **Upload PDF**: `POST /upload`
   - Upload file lên MinIO: `{session_id}/{filename}.pdf`
   - Lưu metadata vào database

2. **Activate File**: `PUT /update-file-active`
   - Download PDF từ MinIO
   - Parse PDF → docs
   - Upload docs lên MinIO: `{session_id}/{file_id}_docs.txt`
   - Embedding vào vector store

3. **View File**: `GET /view-file`
   - Download PDF từ MinIO
   - Convert sang images
   - Return base64 images

4. **Upload Crop**: `POST /upload-crop`
   - Upload ảnh crop lên MinIO: `{session_id}/crop_{file_id}_{filename}`

5. **Delete File**: `DELETE /delete-file/{file_id}`
   - Xóa PDF: `{session_id}/{filename}.pdf`
   - Xóa docs: `{session_id}/{file_id}_docs.txt`
   - Xóa crop images: `{session_id}/crop_{file_id}_*`
   - Xóa metadata trong database

6. **Delete Session**: `DELETE /delete-session/{session_id}`
   - Xóa toàn bộ folder session: `{session_id}/` (bao gồm tất cả PDF, docs, crop images)
   - Xóa tất cả metadata trong database

## Lợi ích

1. **Scalability**: Dễ dàng scale storage độc lập với app server
2. **Backup & Recovery**: MinIO hỗ trợ replication, versioning
3. **Cost-effective**: Lưu trữ object storage rẻ hơn disk
4. **S3 Compatible**: Dễ dàng migrate sang AWS S3, Google Cloud Storage
5. **Distributed**: Hỗ trợ distributed storage

## Migration từ hệ thống cũ

Nếu có dữ liệu cũ trong `/tmp/uploads`, cần migrate sang MinIO:

```python
from app.services.minio_client import minio_client
import os

old_upload_dir = "/tmp/uploads"

for session_id in os.listdir(old_upload_dir):
    session_path = os.path.join(old_upload_dir, session_id)
    if not os.path.isdir(session_path):
        continue
    
    for filename in os.listdir(session_path):
        local_file = os.path.join(session_path, filename)
        
        # Tất cả file đều upload vào folder session
        minio_path = f"{session_id}/{filename}"
        minio_client.upload_file(local_file, minio_path)
        
        print(f"Migrated: {local_file} -> MinIO:{minio_path}")
```

## Troubleshooting

### MinIO Connection Error
```
Error: Unable to connect to MinIO
```
**Solution**: Đảm bảo MinIO server đang chạy tại `localhost:9000`

### Bucket Not Found
```
Error: Bucket 'mybucket' does not exist
```
**Solution**: Tạo bucket `mybucket` qua MinIO Console hoặc restart app để tự động tạo

### File Not Found on MinIO
```
Error: File not found in MinIO
```
**Solution**: Kiểm tra file có tồn tại trong database (`UploadFileStatus`) và MinIO

## Testing

Test MinIO service:

```python
from app.services.minio_client import minio_client

# Test upload
minio_client.upload_file("/path/to/test.pdf", "test/test.pdf")

# Test download
minio_client.download_file("test/test.pdf", "/tmp/test.pdf")

# Test exists
exists = minio_client.file_exists("test/test.pdf")
print(f"File exists: {exists}")

# Test delete
minio_client.delete_file("test/test.pdf")
```

## Notes

- Tất cả các thao tác file giờ đây đều thông qua MinIO
- Local storage chỉ dùng cho file tạm trong quá trình xử lý
- File tạm được xóa ngay sau khi xử lý xong
- Không còn sử dụng `UPLOAD_DIR = "/tmp/uploads"` trong code

