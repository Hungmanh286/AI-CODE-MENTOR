# Kiến trúc

## Thành phần chính
- **FastAPI app** (`main.py`): middleware GZip, `NoBufferingForAgentStream`, CORS; `/ping`, `/apidocs` (Scalar);
  mount mọi router qua `app/api/router.py`.
- **REST** (`app/api/v1/`): auth (`/register`, `/login`), user, progress, lesson, upload/xử lý PDF
  (`/upload`, `/update-file-active`, `/view-file`...), history/session/quiz (`/history-chat`, `/add_answer`...),
  mindmap, SSE `/sse/notify`.
- **Luồng WebSocket cũ** (`app/api/ws/chat.py` → `app/orchestrator/`): graph `agent → tools → END`;
  node agent dùng LLM tool-calling để chọn tool trong `app/agents/registry.py`
  (`document_processing`, `mindmap`, `answer`, `question_generation`, `summary`).
- **Luồng AG-UI mới** (`app/api/agui.py` → `app/agents/mentor_agui/`): `MentorLangGraphAgent` bọc graph
  `router → {qa_rag | summarize | mindmap | quiz_intro → quiz (interrupt) | code_mentor → ui_tools}`.
  Chi tiết: `docs/AG-UI.md`.
- **Services** (`app/services/`): quiz, mindmap, events, và `agui_*` (tài liệu phiên, artifact, lịch sử cũ, phân quyền).
- **Infra** (`app/infra/`): MinIO client, Redis rate limit (`UserUsage`), Qdrant + parse PDF song song,
  checkpointer Postgres cho AG-UI.

## Luồng chạy chính (request/job đi qua những đâu)
1. **Tải tài liệu:** `POST /upload` → lưu file lên MinIO + bản ghi `upload_file_status`.
   `PUT /update-file-active` → PDF thành ảnh (pdf2image) → chia chunk → Gemini qua OpenRouter parse song song
   (`RunnableLambda.batch`) → split markdown → embedding VoyageAI → Qdrant (collection = `session_id`).
   Chunk nào lỗi thì trả `error`, file vẫn chưa xử lý.
2. **Chat WebSocket:** `WS /chat/pedagogical` (JWT) → kiểm tra rate limit Redis → `invoke_workflow`
   chạy graph orchestrator (checkpoint Postgres theo `thread_id = session_uuid`) → stream trả lời → cập nhật token usage.
3. **Chat AG-UI:** `POST /agent` (`RunAgentInput`, Bearer JWT nếu `AGENT_AUTH_REQUIRED`) → router chọn node
   theo chip `requested_tools` hoặc phân loại intent → RAG trên Qdrant của phiên / sinh quiz / mindmap →
   stream event SSE (text, `REASONING_*`, tool call UI, state). `GET /threads/{id}/messages` dựng lại lịch sử.

## Dữ liệu và lưu trữ
- **PostgreSQL app** (`APP_DB_*`, cổng 5435): bảng `user`, `progressuser`, `lesson`, `upload_file_status`,
  `mindmaps`, `agent_mindmaps`, `projects`, `questions`, `question_options`, `session_projects`.
  Tạo bằng `SQLModel.metadata.create_all` lúc khởi động (không có migration).
- **PostgreSQL checkpointer** (`CHECKPOINT_*`, cổng 5434): checkpoint graph WebSocket; AG-UI dùng schema riêng `mentor_agui`.
- **Qdrant**: một collection cho mỗi session; chunk mới có `file_id`/`file_name`.
- **MinIO**: file PDF gốc, ảnh mind map (luồng cũ).
- **Redis** (cổng 6380 theo compose): rate limit và token usage theo user.
- **Tài khoản**: `app/core/settings/user.json` (`ACCOUNT_FILE`). TODO: xác nhận còn dùng song song với bảng `user` không.
- `var/`: output runtime (log, mindmap, kết quả eval).

## Phụ thuộc bên ngoài (API, dịch vụ, queue...)
- **OpenRouter**: LLM chat (`CHAT_MODEL`), model trả lời có reasoning (`CHAT_ANSWER_MODEL`), Gemini parse PDF / mindmap
  (`MIND_MAP_MODEL`, `MIND_MAP_IMAGE_MODEL`).
- **VoyageAI**: embedding (`EMBEDDING_MODEL`, mặc định `voyage-3`).
- **Langfuse**: tracing (tuỳ chọn).
- **DuckDuckGo (`ddgs`)**: agent `web_search`. TODO: xác nhận agent này còn được dùng.
- Chưa có queue; job dài (quiz/mindmap) chạy ngay trong run.
