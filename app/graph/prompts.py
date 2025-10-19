class Prompts:
    """Class Prompt templates."""

    GENERATE_QUESTIONS_PROMPT = """
Bạn là chuyên gia tạo câu hỏi giúp người dùng hiểu nội dung trong Tài liệu nguồn bên dưới.

Yêu cầu:
- Phân tích kỹ câu hỏi của người dùng: {question}
- Không thêm kiến thức ngoài Tài liệu nguồn bên dưới
- Với mỗi mục kiến thức trong bài, hãy tạo 5 câu hỏi đủ mức độ
- Chỉ liệt kê các câu hỏi, không giải thích, không thêm định dạng hoặc số thứ tự
- Câu hỏi ở dạng multi choice
Tài liệu nguồn:
{documents}
    """

    EVALUATE_QUESTIONS_PROMPT = """
Bạn là một giảng viên có chuyên môn trong lĩnh vực lập trình hướng đối tượng.

Nhiệm vụ của bạn là **chọn ra 3 câu hỏi trắc nghiệm tốt nhất cho mỗi mục kiến thức** dựa trên nội dung tài liệu sau:
---
{documents}
---

Danh sách câu hỏi cần đánh giá:
---
{questions}
---

### Cấu trúc dữ liệu yêu cầu:

Bạn phải trả về một **danh sách JSON hợp lệ** (`[...]`) gồm các đối tượng câu hỏi.  
Mỗi đối tượng câu hỏi (question object) bao gồm các trường sau:

1. "id": Mã định danh duy nhất cho câu hỏi (ví dụ: "q1", "q2"...).  
2. "type": Loại câu hỏi.  
3. "difficulty": Mức độ khó của câu hỏi.  
4. "question": Nội dung chính của câu hỏi.  
5. "options": Danh sách 4 lựa chọn trả lời (A, B, C, D).  
6. "correct_answer": Chỉ số của đáp án đúng trong mảng "options".  
Ví dụ: "correct_answer": 0 nghĩa là đáp án đầu tiên là đúng.
7. "explanation": Giải thích ngắn gọn tại sao đáp án đó đúng.  
---
### Ví dụ mẫu (chuẩn định dạng):
[
  {{
    "id": "q1",
    "type": "multiple_choice",
    "difficulty": "medium",
    "question": "Trong lập trình hướng đối tượng, tính đóng gói là gì?",
    "options": [
      "Ẩn thông tin chi tiết của đối tượng và chỉ cung cấp giao diện công khai",
      "Kế thừa thuộc tính từ lớp cha",
      "Gắn kết dữ liệu và hành vi vào cùng một lớp",
      "Tách chương trình thành các hàm riêng lẻ"
    ],
    "correct_answer": 0,
    "explanation": "Tính đóng gói giúp che giấu chi tiết triển khai nội bộ và chỉ lộ ra giao diện công khai."
  }},
  {{
    "id": "q2",
    "type": "multiple_choice",
    "difficulty": "easy",
    "question": "Khái niệm 'đối tượng' trong lập trình hướng đối tượng biểu thị điều gì?",
    "options": [
      "Một tập hợp các hàm không liên quan",
      "Một thể hiện cụ thể của lớp có dữ liệu và hành vi riêng",
      "Một biến toàn cục trong chương trình",
      "Một kiểu dữ liệu cơ bản"
    ],
    "correct_answer": 1,
    "explanation": "Đối tượng là thể hiện cụ thể của lớp, có dữ liệu và hành vi riêng biệt."
  }}
]

---

### Yêu cầu bắt buộc:
- Trả về **chính xác một danh sách JSON hợp lệ** (`[...]`), **không kèm theo mô tả, tiêu đề hoặc định dạng Markdown**.
- Mỗi mục kiến thức chỉ chọn **3 câu hỏi trắc nghiệm tốt nhất**.
- Mỗi câu hỏi phải có đầy đủ các trường trên.
- Câu hỏi phải rõ ràng, bám sát nội dung tài liệu, có giá trị sư phạm và phù hợp trình độ sinh viên.
- Không thêm bình luận, giải thích, hay văn bản nào ngoài danh sách JSON.
"""
