class Prompts:
    """Class Prompt templates."""

    GENERATE_QUESTIONS_PROMPT = """
Bạn là chuyên gai tạo câu hỏi giúp cho người dùng hiểu được tất cả nội dung trong Tài liệu nguồn bên dưới
Yêu cầu:
- Không thêm kiến thức ngoài tài liệu.
- Tóm tắt Tài liệu nguồn bên dưới
- Với mối mục kiến thức trong bài hãy tạo 3 câu hỏi đủ mức độ
    
Tài liệu nguồn:
{documents}
    """
