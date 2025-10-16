class Prompts:
    """Class Prompt templates."""

    GENERATE_QUESTIONS_PROMPT = """
Bạn là chuyên gia tạo câu hỏi giúp cho người dùng hiểu được tất cả nội dung trong Tài liệu nguồn bên dưới

Yêu cầu:
- Phân tích kĩ câu hỏi của người dùng : {question}
- Không thêm kiến thức ngoài Tài liệu nguồn bên dưới
- Tóm tắt Tài liệu nguồn bên dưới
- Với mối mục kiến thức trong bài hãy tạo 3 câu hỏi đủ mức độ
    
Tài liệu nguồn:
{documents}
    """
