# AI Code Mentor

AI Code Mentor là backend FastAPI cho hệ thống trợ lý học tập và hỏi đáp tài liệu. Dự án kết hợp LangGraph/LangChain, WebSocket chat, xử lý PDF, vector search, sinh mind map, quản lý người dùng và giới hạn token theo người dùng.

## Tính năng chính

- Chat realtime qua WebSocket tại `/chat/pedagogical`.
- Workflow tác tử bằng LangGraph để định tuyến yêu cầu tới các tool xử lý tài liệu, hỏi đáp, tóm tắt, mind map và tạo câu hỏi.
- Upload PDF, lưu file qua MinIO, parse nội dung PDF bằng Gemini qua OpenRouter.
- Xử lý PDF song song bằng `RunnableLambda.batch(..., config={"max_concurrency": ...})`.
- Embedding nội dung tài liệu bằng VoyageAI và lưu vào Qdrant.
- Checkpoint hội thoại bằng PostgreSQL.
- Rate limit/token usage bằng Redis.
- Theo dõi LLM trace qua Langfuse.
- API docs bằng Scalar tại `/apidocs`.

## Công nghệ

- Python 3.11+
- FastAPI
- LangChain, LangGraph
- OpenRouter/Gemini
- VoyageAI Embeddings
- Qdrant
- PostgreSQL
- Redis
- MinIO
- SQLModel
- Langfuse

## Cấu trúc thư mục

```text
.
├── app/
│   ├── config.py                 # Cấu hình môi trường và kết nối hệ thống
│   ├── routes/                   # FastAPI routers
│   ├── graph/                    # LangGraph workflow, nodes, prompts, agents
│   ├── services/                 # MinIO, vector store, auth, rate limit, datasource
│   ├── schema/                   # SQLModel/Pydantic schemas
│   └── data/                     # Dữ liệu mẫu và tài liệu thử nghiệm
├── tests/                        # Test scripts
├── docs/                         # Tài liệu bổ sung
├── examples/                     # Ví dụ
├── main.py                       # FastAPI entrypoint
├── pyproject.toml                # Dependencies cho uv
├── docker-compose.yml            # Redis và PostgreSQL phụ trợ
└── README.md
```

## Yêu cầu hệ thống

- Python 3.11 trở lên.
- `uv` để cài dependencies.
- Redis cho rate limiting.
- PostgreSQL cho app database và LangGraph checkpointer.
- Qdrant chạy tại `localhost:6333` hoặc URL tương ứng trong code/config.
- MinIO chạy tại endpoint cấu hình trong `.env`.
- Poppler để `pdf2image` chuyển PDF sang ảnh.

Trên Ubuntu/Debian, Poppler thường có thể cài bằng:

```bash
sudo apt-get install poppler-utils
```

## Cài đặt

1. Cài dependencies:

```bash
uv sync
```

2. Tạo file môi trường:

```bash
cp .env.example .env
```

3. Cập nhật các biến quan trọng trong `.env`:

```env
OPENROUTER_API_KEY=...
EMBEDDING_KEY=...
SECRET_KEY=...
CHECKPOINT_PASSWORD=...
APP_PASSWORD=...
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=admin
MINIO_SECRET_KEY=admin123
MINIO_BUCKET=mybucket
MIND_MAP_MODEL=gemini-2.5-flash
```

Không commit secret thật vào repository.

## Chạy dịch vụ phụ trợ

`docker-compose.yml` hiện khai báo Redis và hai PostgreSQL service:

```bash
docker compose up -d codeMentor-ratelimit codeMentor-checkpointer codeMentor-app
```

MinIO và Qdrant cần được chạy riêng nếu môi trường local chưa có sẵn. Ví dụ:

```bash
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant
docker run -d --name minio -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=admin \
  -e MINIO_ROOT_PASSWORD=admin123 \
  minio/minio server /data --console-address ":9001"
```

## Chạy ứng dụng

```bash
uv run python main.py
```

Hoặc:

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8686 --reload
```

Kiểm tra health check:

```bash
curl http://localhost:8686/ping
```

Mở API docs:

```text
http://localhost:8686/apidocs
```

## Các endpoint chính

- `GET /ping`: health check.
- `GET /apidocs`: Scalar API documentation.
- `WS /chat/pedagogical`: chat realtime với agent.
- `POST /upload`: upload PDF lên MinIO và ghi metadata.
- `PUT /update-file-active`: kích hoạt file, parse PDF, lưu docs và embedding vào Qdrant.
- `GET /session-files/{session_id}`: lấy danh sách file theo session.
- `GET /view-file`: xem PDF đã upload dưới dạng ảnh base64.
- `GET /get-mindmap`: lấy mind map dạng base64.
- `GET /get-mindmap-url`: lấy presigned URL cho mind map.

## Cấu hình PDF parsing

Các cấu hình xử lý PDF nằm trong `app/config.py` và có thể override qua `.env`:

```env
PDF_PARSE_MAX_WORKERS=50
PDF_PARSE_RPM_LIMIT=500
PDF_PARSE_CHUNK_SIZE_SMALL=15
PDF_PARSE_CHUNK_SIZE_LARGE=30
PDF_PARSE_CHUNK_SIZE_THRESHOLD=50
PDF_PARSE_RETRY_ATTEMPTS=3
PDF_PARSE_RETRY_DELAY=2
```

Parser PDF hiện chỉ dùng Gemini qua OpenRouter. Mỗi chunk được xử lý bằng LangChain runnable batch:

```python
chunk_processor.batch(
    chunks_data,
    config={"max_concurrency": max_concurrency},
)
```

## Kiểm tra nhanh

Compile các file Python:

```bash
uv run python -m py_compile main.py app/config.py app/services/vector_store_parallel.py
```

Chạy test script xử lý PDF nếu có file mẫu và API key hợp lệ:

```bash
uv run python tests/test_parallel_processing.py
```

## Ghi chú vận hành

- WebSocket chat yêu cầu JWT token hợp lệ.
- Redis được dùng để kiểm soát token usage/rate limit.
- PostgreSQL checkpointer lưu trạng thái hội thoại theo `thread_id`.
- Qdrant cần chạy trước khi embedding tài liệu.
- MinIO cần sẵn sàng trước khi upload/view/delete file.
- Langfuse keys là tùy chọn theo môi trường tracing, nhưng nếu bật tracing thì cần cấu hình đúng.
