# Code Convention & Development Guidelines

Tài liệu này quy định các chuẩn mực lập trình, quy trình làm việc và các hướng dẫn phát triển cho dự án. Mục tiêu là đảm bảo tính nhất quán, dễ bảo trì và chất lượng cao của mã nguồn khi làm việc nhóm.

## 1. Cấu trúc Dự án (Project Structure)

Dự án tuân theo cấu trúc module hóa, tách biệt rõ ràng giữa các tầng logic.

```
root/
├── app/                    # Source code chính của ứng dụng
│   ├── config/             # Các file cấu hình (JSON, sample)
│   ├── db/                 # Database models (SQLModel) và logic liên quan
│   ├── graph/              # Logic LangGraph (Nodes, Agents, Tools, Workflow)
│   ├── routes/             # FastAPI Routes (Controllers)
│   ├── schema/             # Pydantic Models (Request/Response schemas)
│   ├── services/           # Business Logic Layer (xử lý nghiệp vụ chính)
│   ├── config.py           # Cấu hình Global (Pydantic Settings)
│   ├── log.py              # Cấu hình Logging (Structlog)
│   └── main.py             # Entry point của ứng dụng
├── data/                   # Dữ liệu tĩnh (CSV, etc.)
├── db_setup/               # SQL scripts khởi tạo DB
├── docs/                   # Tài liệu dự án (MkDocs)
├── scripts/                # Utility scripts (migration, data processing)
├── tests/                  # Unit tests và Integration tests
├── pyproject.toml          # Quản lý dependencies và cấu hình tool (Ruff, Pytest)
└── docker-compose.yml      # Cấu hình Docker
```

## 2. Môi trường Phát triển (Development Environment)

Khuyến khích sử dụng **uv** để quản lý môi trường và dependencies vì tốc độ và tính tương thích cao.

### 2.1. Cài đặt & Quản lý Dependencies

* **Python Version**: `>=3.12`
* **Tool**: `uv` (thay thế cho pip/poetry).

**Khởi tạo môi trường:**

```bash
# Cài đặt uv (nếu chưa có)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Tạo virtual environment
uv init

# Đồng bộ môi trường
uv sync
```

### 2.2. IDE Setup

* IDE Khuyến nghị: **VS Code**
* Cài đặt extension: Python, Pylance, Ruff.

## 3. Quy tắc Đặt tên (Naming Conventions)

Tuân thủ chuẩn PEP 8 với một số quy định cụ thể:

| Thành phần | Quy tắc | Ví dụ |
| :--- | :--- | :--- |
| **File/Module** | `snake_case` | `chat_service.py`, `user_model.py` |
| **Class** | `PascalCase` | `ChatService`, `UserProfile`, `GlobalConfig` |
| **Function/Method** | `snake_case` | `get_user_by_id`, `process_message` |
| **Variable** | `snake_case` | `user_info`, `message_count` |
| **Constant** | `UPPER_CASE` | `MAX_RETRY`, `DEFAULT_TIMEOUT` |
| **Private Member** | `_snake_case` (prefix `_`) | `_initialize_db`, `_cache_client` |

**Lưu ý:**

* Tên phải mang ý nghĩa rõ ràng, tránh viết tắt trừ những từ phổ biến (như `id`, `url`, `api`).
* Tên biến boolean nên bắt đầu bằng `is_`, `has_`, `can_` (ví dụ: `is_active`, `has_permission`).

## 4. Code Style & Formatting

Dự án sử dụng **Ruff** để enforce code style.

### 4.1. Formatting

* **Line Length**: 100 ký tự (cấu hình trong pyproject.toml).
* **Indentation**: 4 spaces.
* **Quotes**: Double quotes `"` cho string.

### 4.2. Imports

Sắp xếp import theo thứ tự sau, mỗi nhóm phân tách nhau 1 dòng trống:

1. **Standard Library**: `import os`, `import sys`
2. **Third-party Libraries**: `from fastapi import APIRouter`
3. **Local Application Imports**: `from app.services import ChatService`

Sử dụng Absolute Import (from app.x import y) thay vì Relative Import (from ..x import y) để dễ refactor và tra cứu.

### 4.3. Type Hinting

* **Bắt buộc** sử dụng Type Hints cho arguments và return types.
* Sử dụng typing.Optional, typing.List, typing.Dict hoặc cú pháp mới | (Python 3.10+) nếu có thể.

```python
# Tốt
def get_user(user_id: str) -> User | None: ...


# Không tốt
def get_user(user_id): ...
```

### 4.4. Docstrings

* Sử dụng **Google Style** docstrings cho public modules, classes, functions.
* Mô tả ngắn gọn mục đích, danh sách tham số (Args), giá trị trả về (Returns).

```python
def calculate_score(points: int, bonus: int = 0) -> int:
    """Calculate the total score based on points and bonus.

    Args:
        points: The base points.
        bonus: The bonus points to add. Defaults to 0.

    Returns:
        The total calculated score.
    """
    return points + bonus
```

## 5. Asynchronous Programming (Quan trọng)

Do sử dụng FastAPI và LangGraph, việc xử lý bất đồng bộ là bắt buộc để đảm bảo hiệu năng.

* **Async/Await**: Sử dụng `async def` cho tất cả các route handlers và các function có thực hiện I/O (DB query, gọi API ngoại vi).
* **Non-blocking**: Tránh sử dụng các hàm blocking (như `time.sleep`, `requests.get`) trong `async def`. Thay vào đó dùng `asyncio.sleep`, `httpx.AsyncClient`.
* **Database**: Sử dụng `AsyncSession` với SQLAlchemy/SQLModel.

```python
# Đúng
async def get_data():
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com")
        return response.json()


# Sai (Block event loop)
async def get_data():
    response = requests.get("https://api.example.com")
    return response.json()
```

## 6. Logging & Error Handling

### 6.1. Logging

* **KHÔNG** sử dụng `print()`.
* Sử dụng `app.log.logger` (structlog) cho mọi hoạt động ghi log.
* * Kèm theo context (ví dụ: `trace_id`, `user_id`) để dễ trace lỗi (có thể inject từ middleware).
* Log level phù hợp:
  * `DEBUG`: Thông tin chi tiết để debug.
  * `INFO`: Thông tin luồng hoạt động bình thường.
  * `WARNING`: Vấn đề tiềm ẩn nhưng app vẫn chạy được.
  * `ERROR`: Lỗi nghiệp vụ hoặc runtime error cần chú ý.
  * `FATAL`: Lỗi nghiêm trọng khiến app dừng hoạt động.

```python
from app.log import logger

logger.info("processing_request", user_id=user_id, action="chat")
try:
    ...
except Exception as e:
    logger.error("request_failed", error=str(e), user_id=user_id)
```

### 6.2. Error Handling

* Catch specific exceptions nếu có thể.
* Sử dụng `HTTPException` trong routes.
* Tạo Custom Exception trong `app/error.py` cho các lỗi nghiệp vụ (Business Logic Errors).

## 7. Configuration & Secrets

* Tất cả cấu hình phải được định nghĩa trong `app/config.py` sử dụng `pydantic-settings`.
* **TUYỆT ĐỐI KHÔNG** hardcode mật khẩu, API key, token trong code.
* Sử dụng file `.env` để lưu biến môi trường local. File `.env` phải được thêm vào `.gitignore`.
* Truy cập cấu hình thông qua object `settings`:

```python
from app.config import settings

api_key = settings.CHAT_MODEL_KEY
```

## 8. Database & Schema

* **Models**: Sử dụng SQLModel cho ORM, có thể tái sử dụng cho FastAPI Schema. Tên bảng (table name) nên là số nhiều (`users`, `messages`).
* **Schemas**:
  * Tách biệt schema cho Request (Input) và Response (Output) nếu cấu trúc khác nhau.
  * Sử dụng `Field` để mô tả metadata (default, example, description) cho API documentation tự động.

## 9. FastAPI Architecture & Best Practices

Để đảm bảo ứng dụng có khả năng mở rộng và bảo trì tốt, cần tuân thủ các nguyên tắc thiết kế sau của FastAPI:

### 9.1. Dependency Injection (`Depends`)

* **Ưu tiên sử dụng `Depends`**: Thay vì khởi tạo service hoặc kết nối DB trực tiếp trong route, hãy sử dụng cơ chế Dependency Injection. Để dễ dàng mock khi test, quản lý vòng đời object tốt hơn, code gọn gàng.

```python
# Tốt: Sử dụng Depends để inject service
async def get_chat_response(
    message: str, chat_service: ChatService = Depends(get_chat_service)
):
    return await chat_service.process(message)


# Không tốt: Khởi tạo trực tiếp
async def get_chat_response(message: str):
    service = ChatService()  # Khó test, khó quản lý connection
    return await service.process(message)
```

### 9.2. Lifespan Events

* **Ưu tiên sử dụng `lifespan` context manager**: Như khởi tạo kết nối DB, load ML models, setup cache khi app khởi động và dọn dẹp khi tắt, dễ kiếm soát tài nguyên.

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Load resources
    await db.connect()
    ml_models = load_models()
    yield
    # Shutdown: Clean up
    await db.disconnect()
    ml_models.clear()


app = FastAPI(lifespan=lifespan)
```

### 9.3. Middleware

* **Sử dụng Middleware cho Cross-cutting Concerns**: Các logic áp dụng cho toàn bộ request như logging, CORS, authentication, error handling, timing nên được đặt ở middleware.
* **Thứ tự**: Lưu ý thứ tự add middleware (cái nào add sau chạy trước).

```python
# Ví dụ middleware đo thời gian xử lý, thêm log context request-id
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response
```

## 10. API Design Guidelines

* **RESTful**: Sử dụng đúng HTTP methods (`GET`, `POST`, `PUT`, `DELETE`).
* **URL Naming**: Danh từ số nhiều, chữ thường, gạch nối (`/api/v1/users`, `/api/v1/chat-history`).
* **Status Codes**:
  * `200 OK`: Thành công.
  * `201 Created`: Tạo mới thành công.
  * `400 Bad Request`: Lỗi dữ liệu đầu vào.
  * `401 Unauthorized`: Chưa đăng nhập.
  * `403 Forbidden`: Không có quyền.
  * `404 Not Found`: Không tìm thấy tài nguyên.
  * `500 Internal Server Error`: Lỗi server.
  * ...

## 11. LangGraph & AI Components

* **Prompts**: Không hardcode prompt dài trong code logic. Lưu trong `app/graph/prompts.py` hoặc file text riêng biệt.
* **State**: State của graph phải được định nghĩa rõ ràng trong `app/graph/state.py`. Tránh lưu trữ dữ liệu dư thừa trong state.
* **Nodes**: Mỗi node nên thực hiện một nhiệm vụ cụ thể (Single Responsibility).

## 12. Testing

* **Framework**: `pytest`.
* **Vị trí**: Thư mục `tests/`.
* **Naming**: File test bắt đầu bằng `test_`. Function test bắt đầu bằng `test_`.
* **Scope**:
  * Unit Test: Test logic nhỏ, mock các dependencies (DB, API).
  * Integration Test: Test luồng API, có thể kết nối DB test.

## 13. Git Workflow

### 13.1. Branching

* `main`: Code production-ready, ổn định.
* `dev`: Branch phát triển chính.
* `feature/tên-tính-năng`: Branch cho tính năng mới (tách từ `dev`).
* `fix/tên-lỗi`: Branch sửa lỗi.

### 13.2. Commit Messages

Tuân thủ **Conventional Commits**:
`<type>(<scope>): <description>`

Các loại `type`:

* `Feat`: Tính năng mới.
* `Fix`: Sửa lỗi.
* `Docs`: Thay đổi tài liệu.
* `Style`: Format code, không thay đổi logic.
* `Refactor`: Cấu trúc lại code, không đổi tính năng.
* `Chore`: Cập nhật build task, package manager, etc.

Ví dụ:

* `Feat(chat): add support for image input`
* `Fix(auth): resolve token expiration issue`
* `Docs(readme): update installation guide`

### 13.3. Pull Requests (PR)

* Tạo PR từ branch feature vào `dev`.
* **LUÔN LUÔN** Pull code từ `dev` về branch làm việc trước khi push.
* Chạy lại ứng dụng để đảm bảo mọi thứ hoạt động trước khi push.
* Cần báo reviewer approve để có thể merge.

## 14. Ignore

* File `.gitignore` cho git để tránh tracking bỏ các file rác, file logs sinh ra, hay file env (quan trọng) và các dữ liệu nhạy cảm...
* File `.dockerignore` cho docker để giảm kích thước image khi build, không đưa các thông tin nhạy cảm vào image

## 15. Tài liệu (Documentation)

* Cập nhật `README.md` khi có thay đổi về cách cài đặt hoặc chạy dự án.
* Viết tài liệu API trong thư mục `docs/` (sử dụng MkDocs).
* Code mới phải đi kèm docstrings đầy đủ.

---
*Yêu cầu các thành viên dự án có trách nhiệm tuân thủ nghiêm ngặt.*
