# Cập nhật cấu trúc folder MinIO

## ✅ Hoàn tất

Tất cả file liên quan đến một session giờ đây được lưu trong **cùng 1 folder** trên MinIO.

## 📁 Cấu trúc cũ (trước khi cập nhật)

```
mybucket/
├── {session_id}/
│   ├── {filename}.pdf
│   └── crop_{file_id}_{filename}
└── {file_id}_{session_id}_docs.txt        ❌ Nằm ngoài folder session
```

## 📁 Cấu trúc mới (sau khi cập nhật)

```
mybucket/
└── {session_id}/                          ✅ MỌI FILE TRONG 1 FOLDER
    ├── {filename}.pdf                     ✅ File PDF gốc
    ├── {file_id}_docs.txt                 ✅ Docs đã parse (moved vào folder)
    └── crop_{file_id}_{filename}          ✅ Ảnh crop (nếu có)
```

## 🔄 Files đã cập nhật

### 1. Upload & Process Files
**File**: `app/routes/upload_pdf.py`

**Thay đổi**:
```python
# CŨ
docs_minio_path = f"{file_id}_{session_id}_docs.txt"  # Root level

# MỚI
docs_minio_path = f"{session_id}/{file_id}_docs.txt"  # Inside session folder
```

### 2. Read Docs - Document Processing
**File**: `app/graph/agents/document_processing.py`

**Thay đổi**:
```python
# CŨ
docs_minio_path = f"{file_id}_{session_id}_docs.txt"

# MỚI
docs_minio_path = f"{session_id}/{file_id}_docs.txt"
```

### 3. Read Docs - Question Expert
**File**: `app/graph/agents/question_expert.py`

**Thay đổi**:
```python
# CŨ
docs_minio_path = f"{file_id}_{session_id}_docs.txt"

# MỚI
docs_minio_path = f"{session_id}/{file_id}_docs.txt"
```

### 4. Read Docs - Summarize Agent
**File**: `app/graph/agents/summarize_agent.py`

**Thay đổi** (2 nơi: `summarize_node` và `extractive_node`):
```python
# CŨ
docs_minio_path = f"{file_id}_{session_id}_docs.txt"

# MỚI
docs_minio_path = f"{session_id}/{file_id}_docs.txt"
```

### 5. Delete Files
**File**: `app/routes/process_data.py`

**Thay đổi**:
```python
# CŨ
docs_path = f"{file_id}_{session_id}_docs.txt"
# Xóa từng file crop riêng lẻ

# MỚI
docs_path = f"{session_id}/{file_id}_docs.txt"
# Xóa toàn bộ folder session
all_session_files = minio_client.list_files(prefix=f"{session_id}/")
for file_path in all_session_files:
    minio_client.delete_file(file_path)
```

## 🎯 Lợi ích

1. **Dễ quản lý**: Tất cả file của 1 session nằm trong 1 folder
2. **Dễ xóa**: Xóa session = xóa cả folder, không sót file
3. **Rõ ràng**: Biết ngay file nào thuộc session nào
4. **Tổ chức tốt**: Không có file lẻ tẻ ở root level
5. **Backup dễ**: Backup theo session, không sót file

## 📊 Ví dụ thực tế

### Session: `user123_20250121`

**Trước**:
```
mybucket/
├── user123_20250121/
│   └── lecture.pdf
└── file456_user123_20250121_docs.txt    # Riêng lẻ ở ngoài
```

**Sau**:
```
mybucket/
└── user123_20250121/
    ├── lecture.pdf
    ├── file456_docs.txt                 # Cùng folder
    └── crop_file456_page1.png           # Cùng folder
```

### Xóa session

**Trước**: Phải xóa từng file:
```python
minio_client.delete_file(f"{session_id}/{file_name}")
minio_client.delete_file(f"{file_id}_{session_id}_docs.txt")  # Khác folder
minio_client.delete_file(...)  # Nhiều lần
```

**Sau**: Xóa cả folder:
```python
all_files = minio_client.list_files(prefix=f"{session_id}/")
for file in all_files:
    minio_client.delete_file(file)  # 1 lần cho tất cả
```

## ✅ Không có lỗi Lint

Tất cả files đã pass kiểm tra lint!

## 🚀 Deploy ngay

Code đã sẵn sàng để deploy. Không cần thay đổi gì thêm.

