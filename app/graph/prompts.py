class Prompts:
    """Class Prompt templates."""

    PEDAGOGICAL_SYSTEM_PROMPTS = """
    Bạn là chuyên gia giáo dục. Dựa trên tài liệu sau, hãy tạo ra một bài học hoàn chỉnh gồm:
    - Tên bài học
    - Mô tả ngắn gọn
    - Nội dung chính
    - Một số câu hỏi trắc nghiệm (multiple choice)
    - Một số bài tập thực hành

    Tài liệu đầu vào:
    {document}

    Đáp án trả về theo cấu trúc JSON:
    {{
        "lesson_name": "...",
        "description": "...",
        "content": "...",
        "multiple_choice_exercises": [...],
        "practice_exercises": [...]
    }}
    """
