# Tiến độ (cập nhật: 2026-11-22)

## Đang làm
- Đã commit khung project (CLAUDE.md, docs/ARCHITECTURE.md, docs/PROGRESS.md, docs/decisions/ 001-003).
- Nhánh `ag-ui`: tích hợp agent AG-UI (`POST /agent`) chạy song song luồng WebSocket.

## Đã xong gần đây
- `afb2a22` sửa lỗi parse PDF, mind map, tham số quiz; stream reasoning của câu trả lời.
- `d0949f8` không trích dẫn marker lỗi parse PDF như nội dung tài liệu.
- `a7f8b12` đọc lịch sử phiên cũ, log mỗi run, stream không buffer, tài liệu AG-UI.
- `c818573` lưu quiz và mind map vào DB, giới hạn job, nối chip.
- `91b3db9` trả lời bằng LLM thật, tài liệu của phiên, trích dẫn.

## Quyết định đã chốt (chi tiết trong `docs/decisions/`)
- 001: ghim `ag-ui-langgraph==0.0.47` (override method protected).
- 002: checkpoint AG-UI tách schema riêng, không dùng chung bảng với graph WebSocket.
- 003: giữ luồng WS `/chat/pedagogical` ít nhất một chu kỳ phát hành để rollback.

## Vấn đề còn mở
- Mật khẩu tài khoản `mentor` từng bị push (commit cũ `168c28e`, PR #5). History `main`/`ag-ui`
  đã viết lại (force-push 2026-11-22) nhưng GitHub vẫn giữ ref PR #5: cần đổi mật khẩu và nhờ
  GitHub Support xoá ref/cache của PR #5.
- `app/core/settings/user.json` đã untrack + gitignore, nhưng vẫn còn trong history cũ.
- `README.md` còn marker merge conflict (`<<<<<<<`, `>>>>>>>`) ở cuối file.
- `docker-compose.yml` trỏ tới `Dockerfile` ở gốc nhưng file không tồn tại (cả trong `deploy/`).
- `.env.example`/config mặc định Redis `localhost:6379`, compose map ra cổng `6380`.
- `docs/AG-UI.md` ghi `AGENT_AUTH_REQUIRED` mặc định `false`, code (`app/core/config.py`) là `True`.

## Đã xử lý
- Nhánh tích hợp là `main`: `ag-ui` vào `main` qua PR (PR #5, PR #6).
- CI chỉ chạy `pytest tests/unit` và fail thật khi test đỏ (trước đây `pytest -v || echo`).

## Bước tiếp theo
- Theo `docs/AG-UI.md` mục 7: bật AG-UI ở staging rồi production; bật auth khi `/login` trả JWT;
  worker cho job dài (Kafka/Redis Streams).
