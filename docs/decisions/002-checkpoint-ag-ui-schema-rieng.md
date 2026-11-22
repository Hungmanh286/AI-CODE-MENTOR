# 002: Checkpoint AG-UI dùng schema Postgres riêng
- Ngày: 2026-11-19 (commit `c4a8c74`)
- Bối cảnh: graph AG-UI (`mentor_agui`) và graph WebSocket cũ đều dùng `thread_id = session_uuid`,
  nhưng có node và kênh state khác nhau. Nếu dùng chung bảng checkpoint, graph này sẽ đọc phải
  state của graph kia, gây lỗi hoặc làm hỏng lịch sử hội thoại.
- Quyết định: checkpoint AG-UI nằm trong schema riêng `MENTOR_CHECKPOINT_SCHEMA` (mặc định
  `mentor_agui`) của DB checkpoint, tự tạo khi khởi động (`app/infra/agui_checkpointer.py`).
- Lý do / phương án đã loại:
  - Dùng chung bảng, đổi `thread_id` (thêm tiền tố): bị loại vì vẫn chung bảng, dễ đụng nhau
    khi có bug, và khó dọn dữ liệu của một luồng.
  - Dùng hẳn một database khác: bị loại vì thêm hạ tầng không cần thiết.
- Hệ quả: phiên cũ không tự có lịch sử bên AG-UI. `/threads` đọc checkpoint WS ở chế độ chỉ đọc
  (id `legacy-{session}-{i}-u|a`) và chép sang checkpoint mới ở run đầu tiên
  (`app/services/agui_legacy_history.py`).
