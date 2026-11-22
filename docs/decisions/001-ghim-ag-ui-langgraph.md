# 001: Ghim chính xác `ag-ui-langgraph==0.0.47`
- Ngày: 2026-11-19 (commit `6e17bdf`)
- Bối cảnh: `MentorLangGraphAgent` (`app/agents/mentor_agui/`) kế thừa agent của `ag-ui-langgraph`
  và ghi đè các method protected hoặc chưa có tài liệu. Thư viện còn ở giai đoạn 0.0.x, các method
  này có thể đổi tên hay đổi chữ ký giữa các bản vá mà không báo trước.
- Quyết định: ghim đúng phiên bản `==0.0.47` trong `pyproject.toml`, không dùng `>=` hay `~=`.
- Lý do / phương án đã loại:
  - `>=0.0.47`: bị loại vì một lần `uv sync` có thể kéo bản mới làm hỏng override một cách âm thầm.
  - Tự viết lại adapter AG-UI không dùng thư viện: tốn công và phải tự theo kịp giao thức.
- Hệ quả: muốn nâng phiên bản phải đọc changelog, sửa override nếu cần, rồi chạy
  `uv run python -m scripts.agui_selfcheck` và `uv run pytest tests/unit -q`.
  LangGraph cũng được nâng cùng lúc để tương thích (cùng commit).
