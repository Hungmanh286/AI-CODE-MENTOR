# 003: Giữ luồng WebSocket song song với AG-UI để rollback
- Ngày: 2026-11-19 (commit `c4a8c74`)
- Bối cảnh: luồng mới `POST /agent` (AG-UI, SSE) thay cho WebSocket `/chat/pedagogical`.
  Frontend chọn luồng bằng cờ `VITE_USE_AGUI`. Luồng mới chưa được chạy ở production.
- Quyết định: giữ nguyên WS `/chat/pedagogical`, `/history-chat`, SSE `/sse/notify` và REST cũ
  ít nhất một chu kỳ phát hành sau khi bật AG-UI ở production (`docs/AG-UI.md` mục 7).
- Lý do / phương án đã loại:
  - Thay hẳn luồng cũ trong một lần: bị loại vì nếu AG-UI lỗi ở production thì không có đường lui
    nhanh (chỉ cần tắt `VITE_USE_AGUI`).
- Hệ quả: phải bảo trì hai luồng song song một thời gian, và luật của 002 (checkpoint tách riêng)
  là bắt buộc. Khi gỡ luồng cũ thì viết ADR mới thay thế quyết định này.
