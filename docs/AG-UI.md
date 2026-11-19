# Agent AG-UI (`POST /agent`)

> **Người đọc:** người phát triển và vận hành backend Mentor Code.
> **Hợp đồng:** `docs/agui/PLAN.md` mục 4 trong repo frontend `mentor-code-ui`. Kế hoạch triển khai: `docs/agui/BACKEND-PLAN.md` cùng repo.

Backend phục vụ giao thức AG-UI cho frontend assistant-ui (bật bằng `VITE_USE_AGUI=true`). Luồng cũ (WebSocket `/chat/pedagogical`, SSE `/sse/notify`, REST) **giữ nguyên** và chạy song song.

## 1. Endpoint

| Endpoint | Mô tả |
| --- | --- |
| `POST /agent` | Body `RunAgentInput` (camelCase), trả `text/event-stream`. Body sai định dạng trả 400. |
| `GET /threads/{id}/messages` | `{messages, state}`; thread chưa có gì trả đúng `{"messages": []}`. |
| `GET /health` | `{"ok": true}`. (`GET /agent/health` do thư viện tự thêm.) |

`threadId` = `session_uuid` của luồng cũ. CORS trả `Access-Control-Allow-Origin: *` (không dùng credentials; không client nào gửi cookie).

## 2. Cấu hình

| Biến | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `MENTOR_CHECKPOINT_SCHEMA` | `mentor_agui` | Schema riêng trong DB checkpoint (`CHECKPOINT_*`). Tự tạo khi khởi động. |
| `MENTOR_CHECKPOINT_DB_URL` | trống | URL đầy đủ (DB riêng), ghi đè cách trên. |
| `MENTOR_CHECKPOINT_POOL_SIZE` | `10` | Số kết nối tối đa của pool checkpoint. |
| `AGENT_AUTH_REQUIRED` | `false` | Bật thì `/agent` và `/threads/*` cần `Authorization: Bearer <jwt>`; session đã đăng ký cho user khác trả 403. |
| `CHAT_MODEL` | | Model trả lời và sinh dữ liệu (qua OpenRouter). |

Checkpoint AG-UI **không được** dùng chung bảng với graph WebSocket cũ: hai graph cùng dùng `thread_id = session_uuid` nhưng khác node và kênh.

## 3. Kiểm tra

```bash
uv run python -m scripts.agui_selfcheck          # 52 kiểm tra hợp đồng, offline (cũng chạy trong pytest)
uv run pytest tests/unit                          # toàn bộ unit test
# contract test với server thật (chạy tại repo frontend):
node scripts/agui-smoke.mjs http://<host>:8686/agent --contract-only   # kỳ vọng FAIL 0
```

`ag-ui-langgraph` được ghim **chính xác** (`==0.0.47`): `MentorLangGraphAgent` ghi đè method protected hoặc chưa có tài liệu. Mỗi lần nâng phiên bản phải chạy lại self-check.

## 4. Cấu trúc

| File | Vai trò |
| --- | --- |
| `app/agents/mentor_agui/graph.py` | Graph: router, `qa_rag`, `summarize`, `mindmap`, `quiz_intro` → `quiz` (interrupt), `code_mentor` → `ui_tools`; các hook LLM/RAG/lưu trữ |
| `app/agents/mentor_agui/agent.py` | `MentorLangGraphAgent`: 5 điều chỉnh theo hợp đồng + log mỗi run |
| `app/agents/mentor_agui/backends.py` | LLM thật (structured output, retry), tài liệu, lưu trữ |
| `app/agents/mentor_agui/{ui_catalog,schemas,tools,state,history,prompts}.py` | Schema 5 UI tool, draft của LLM, tool, state, chuyển lịch sử, prompt |
| `app/agents/mentor_agui/placeholders.py` | Dữ liệu cố định cho self-check offline (không dùng khi chạy app) |
| `app/services/agui_{documents,artifacts,legacy_history,access}.py` | Tài liệu của phiên, lưu quiz/mindmap, lịch sử phiên cũ, phân quyền |
| `app/infra/agui_checkpointer.py` | Checkpointer Postgres (schema riêng) |
| `app/api/agui.py`, `app/api/cors.py` | Route, lifespan, middleware chống buffer SSE, CORS |

## 5. Hành vi chính

- **Định tuyến:** chip ở ô nhập (`requested_tools`) thắng phân loại intent. Chọn cả hai chip thì vẽ mindmap trước, rồi mới hỏi cấu hình quiz (form quiz dừng run lại, nên để cuối).
- **Tài liệu:** frontend hiện gửi `active_document_ids: []`. Khi đó backend dùng các file đang bật ở khung Nguồn (`upload_file_status.active`). Id do client gửi chỉ được chấp nhận nếu là file của chính phiên đó.
- **Trích dẫn:** đoạn văn lấy từ collection Qdrant của phiên. File tải lên từ bây giờ có `file_id`/`file_name` trên từng chunk. Chunk cũ (không có metadata) chỉ được trích dẫn khi phiên có đúng một file đã xử lý.
- **Quiz:** luôn hỏi `quiz_config` trước. Bộ câu hỏi được lưu vào `projects`/`questions`/`question_options`, nên `/session-projects` thấy được. `show_quiz` dùng id câu hỏi trong DB, để frontend sau này gọi `/add_answer/{qid}`.
- **Mindmap:** cây JSON lưu ở bảng `agent_mindmaps`. Không render PNG, nên Studio cũ không liệt kê các mindmap này.
- **State:** `artifacts` luôn đọc lại từ DB (đầu mỗi run và trong `/threads`). Job của các run trước bị xóa khi bắt đầu run mới. Mọi lỗi khi sinh hoặc lưu đều chuyển job sang `error`.
- **Phiên cũ:** nếu chưa có checkpoint AG-UI, `/threads` đọc checkpoint của graph WebSocket và trả các cặp hỏi/đáp với id cố định `legacy-{session}-{i}-u|a`. Ở run đầu tiên, các message này được lưu vào checkpoint mới (không nhân đôi).
- **Lỗi:** `RUN_ERROR` chỉ chứa câu tiếng Việt chung, kèm `code` (`AGENT_ERROR`). Lỗi gốc ghi vào log.

## 6. Vận hành

- **Log:** mỗi run ghi một dòng `agui run` gồm `thread_id`, `run_id`, `resume`, `nodes`, `duration_ms`, `end` (`RUN_FINISHED` / `RUN_ERROR` / `CANCELLED`), `error_code`, `interrupted`. Dùng dòng này để theo dõi tỉ lệ `RUN_ERROR`.
- **Proxy:** response `/agent` đã có `X-Accel-Buffering: no` và `Cache-Control: no-cache`. Với nginx, cần đặt `proxy_read_timeout` đủ dài cho run chậm (sinh quiz có thể mất 30–60 giây), và `proxy_http_version 1.1`.
- **Nhiều worker:** dùng được, vì checkpoint nằm trong Postgres.
- **Job dài:** quiz/mindmap chạy ngay trong run. Đóng tab hoặc bấm Dừng sẽ hủy job dở; artifact chỉ được tạo khi job xong. Chuyển sang worker (Kafka/Redis Streams) là việc của phase sau.

## 7. Việc còn lại

**Backend:**
1. Chuyển hẳn sang luồng mới (BACKEND-PLAN GĐ5): bật `VITE_USE_AGUI=true` ở staging, rồi production. Giữ WS `/chat/pedagogical` và `/history-chat` ít nhất một chu kỳ phát hành để rollback.
2. Bật `AGENT_AUTH_REQUIRED=true` khi frontend gửi header và `/login` trả JWT (hiện `/login` chưa trả token).
3. Worker cho job dài (Kafka/Redis Streams), lấy trạng thái job từ DB.

**Frontend (`mentor-code-ui`):**
1. Cập nhật hợp đồng PLAN.md mục 4.4 và mock: nhiều chip thì xử lý mindmap trước, rồi quiz.
2. QuizCard gửi đáp án qua `/add_answer/{qid}` (id đã là id trong DB).
3. Thêm header `Authorization` cho `HttpAgent` và history adapter khi bật auth.
