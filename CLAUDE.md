# CodeMentor (AI Code Mentor) — backend

## Tổng quan
- Mục đích: backend cho trợ lý học tập: hỏi đáp trên tài liệu PDF (RAG), tóm tắt, sinh quiz, mind map.
  Frontend ở repo riêng `code-mentor-ui` / `mentor-code-ui`.
- Stack: Python 3.11+, uv, FastAPI, LangGraph/LangChain, OpenRouter (Gemini, GPT), VoyageAI embedding,
  Qdrant, PostgreSQL (app DB + checkpointer), Redis (rate limit), MinIO, SQLModel, Langfuse, AG-UI.
- Hai luồng chat chạy song song: WebSocket cũ `/chat/pedagogical` và AG-UI mới `POST /agent` (SSE).
- Kiến trúc: `docs/ARCHITECTURE.md` (đọc khi cần) · AG-UI chi tiết: `docs/AG-UI.md`
- Tiến độ hiện tại: `docs/PROGRESS.md`

## Lệnh
- Cài đặt: `uv sync` (cần `poppler-utils`), rồi `cp .env.example .env` và điền key.
- Hạ tầng: `docker compose up -d codeMentor-ratelimit codeMentor-checkpointer codeMentor-app codeMentor-minio codeMentor-qdrant`
- Chạy dev: `uv run uvicorn main:app --host 0.0.0.0 --port 8686 --reload`
- Test nhanh (không cần hạ tầng): `uv run pytest tests/unit -q`
- Self-check hợp đồng AG-UI: `uv run python -m scripts.agui_selfcheck`
- Lint/format (giống CI): `uv run ruff check .` và `uv run ruff format --check .`

## Cấu trúc thư mục chính
- `main.py`: entry point FastAPI (lifespan tạo bảng + khởi động AG-UI).
- `app/api/`: chỉ routing/validate; `router.py` là nơi duy nhất mount router; `agui.py` cho `/agent`.
- `app/services/`: nghiệp vụ (quiz, mindmap, events, `agui_*`).
- `app/orchestrator/`: graph LangGraph gốc của luồng WebSocket, chỉ đọc `agents/registry.py`.
- `app/agents/`: mỗi agent một package; `mentor_agui/` là graph của luồng AG-UI.
- `app/infra/`: MinIO, Redis rate limit, Qdrant + parse PDF, checkpointer AG-UI.
- `app/core/`: config (`settings`), paths, logging, security (JWT).
- `app/db/models/`: bảng SQLModel; `app/schemas/`: DTO Pydantic.
- `tests/`: `unit/` (chạy offline, CI) · `integration/` (LLM/DB thật) · `e2e/` (cần app ở :8686).
- `scripts/`: self-check AG-UI, sinh token, MCP server, benchmark.
- `var/`: output runtime (gitignored); `data/`: dữ liệu đầu vào.

## Quy ước code
- Chi tiết đầy đủ trong `CODE_CONVENTION.md`.
- Luật phụ thuộc: `api → services → orchestrator → agents → infra → core → db`.
  `app/agents/**` không bao giờ import `app.api` (`tests/unit/test_structure.py` kiểm tra).
- Prompt riêng agent đặt ở `app/agents/<agent>/prompts.py`; dùng chung ≥2 agent mới lên `agents/common/`.
- Không hardcode đường dẫn tuyệt đối, dùng `app/core/paths.py` (`DATA_DIR`, `VAR_DIR`).
- Config đọc qua `app.core.config.settings`; thêm biến mới thì cập nhật `.env.example`.
- Ruff: line-length 100, rules E,F,I,W,UP,B. Code async không gọi hàm blocking trong event loop.
- Commit theo Conventional Commits, ví dụ `fix(agui): ...`, `feat(agui): ...`.

## Lưu ý riêng
- Sửa file `.py` có thể làm treo server `--reload` ở :8686 (SSE đang mở): test bằng port khác.
- `ag-ui-langgraph` ghim đúng `==0.0.47` vì `MentorLangGraphAgent` override method protected.
  Nâng phiên bản thì phải chạy lại self-check.
- Checkpoint AG-UI nằm ở schema riêng (`MENTOR_CHECKPOINT_SCHEMA`), không dùng chung bảng với graph WS.
- Thay đổi hợp đồng AG-UI (event, tool UI, state) ảnh hưởng frontend: dùng plan mode.
- `PLAN.md` ở gốc (untracked) là kế hoạch cho repo frontend, không phải repo này.
- Không đọc/in nội dung `.env`; `app/core/settings/user.json` chứa tài khoản.
