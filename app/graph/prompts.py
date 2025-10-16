class Prompts:
    """Class Prompt templates."""

    GENERATE_QUESTIONS_PROMPT = """
Bạn là chuyên gia tạo câu hỏi giúp người dùng hiểu nội dung trong Tài liệu nguồn bên dưới.

Yêu cầu:
- Phân tích kỹ câu hỏi của người dùng: {question}
- Không thêm kiến thức ngoài Tài liệu nguồn bên dưới
- Với mỗi mục kiến thức trong bài, hãy tạo 10 câu hỏi đủ mức độ
- Chỉ liệt kê các câu hỏi, không giải thích, không thêm định dạng hoặc số thứ tự
- Câu hỏi ở dạng , multi choice
Tài liệu nguồn:
{documents}
    """
    EVALUATE_QUESTIONS_PROMPT = """
Bạn là một giảng viên có chuyên môn trong lĩnh vực lập trình hướng đối tượng.

Nhiệm vụ của bạn là **chọn ra 3 câu hỏi chất lượng nhất cho mỗi mục kiến thức** dựa trên tài liệu sau:
---
{documents}
---

Danh sách câu hỏi cần đánh giá:
---
{questions}
---

Hãy đánh giá và chỉ liệt kê ra 3 câu hỏi tốt nhất cho mỗi mục kiến thức, không giải thích, không thêm định dạng hoặc số thứ tự. Ưu tiên các câu hỏi rõ ràng, liên quan, phù hợp trình độ và có giá trị sư phạm.
"""
