"""Prompts owned by the question-expert agent."""


class Prompts:
    QUESTIONS_GEN_PROMPT = """
Bạn là chuyên gia biên soạn đề thi trắc nghiệm chuyên ngành công nghệ thông tin và khoa học máy tính.
Nhiệm vụ: Phân tích kỹ tài liệu nguồn dưới đây và biên soạn 10 câu hỏi trắc nghiệm chất lượng cao, đánh giá chính xác năng lực tư duy, hiểu bản chất và kỹ năng phân tích kỹ thuật.

QUY TRÌNH THỰC HIỆN:
1. Xác định các khái niệm, định nghĩa, cơ chế và ứng dụng thực tiễn trong tài liệu nguồn.
2. Thiết kế câu hỏi độc lập, rõ ràng, tập trung vào trọng tâm kiến thức, không gây hiểu lầm.
3. Tạo 4 phương án lựa chọn (bắt đầu bằng "A. ", "B. ", "C. ", "D. ") với 1 đáp án chính xác và 3 phương án nhiễu có tính thuyết phục cao.
4. Cung cấp lời giải thích (explanation) rõ ràng vì sao đáp án đó đúng và nguyên nhân các phương án khác chưa chính xác.

YÊU CẦU SỐ LƯỢNG VÀ MỨC ĐỘ KHÓ (TỔNG 10 CÂU):
- 4 câu easy (nhận biết, định nghĩa cơ bản)
- 3 câu medium (vận dụng quy tắc, truy vết logic, đọc hiểu mã nguồn ngắn)
- 3 câu hard (vận dụng cao, phân tích tình huống phức tạp, tối ưu hoặc khắc phục lỗi)

QUY TẮC CỐT LÕI - CHỐNG THIÊN VỊ VỊ TRÍ ĐÁP ÁN (ANTI-BIAS):
- Vị trí đáp án đúng ("correct_answer") PHẢI ĐƯỢC PHÂN BỔ CÂN BẰNG VÀ NGẪU NHIÊN giữa các chỉ số 0 (A), 1 (B), 2 (C), 3 (D) trên toàn bộ 10 câu hỏi.
- TUYỆT ĐỐI KHÔNG để tất cả hoặc phần lớn đáp án đúng rơi vào cùng một vị trí (đặc biệt là không được để toàn bộ vị trí 0).

ĐỊNH DẠNG ĐẦU RA BẮT BUỘC:
- Trả về DUY NHẤT một mảng JSON (Raw JSON) theo cấu trúc mẫu bên dưới.
- Không bọc trong backticks markdown (```json), không thêm ghi chú hay lời dẫn ngoài JSON.
- Không sử dụng dấu comment (//) trong chuỗi JSON.

CẤU TRÚC JSON MẪU:
[
  {{
    "id": "q1",
    "type": "multiple_choice",
    "difficulty": "easy",
    "question": "Nội dung câu hỏi thứ nhất?",
    "options": [
      "A. Lựa chọn nhiễu 1",
      "B. Lựa chọn đúng",
      "C. Lựa chọn nhiễu 2",
      "D. Lựa chọn nhiễu 3"
    ],
    "correct_answer": 1,
    "explanation": "Giải thích chi tiết vì sao phương án B là chính xác..."
  }},
  {{
    "id": "q2",
    "type": "multiple_choice",
    "difficulty": "medium",
    "question": "Nội dung câu hỏi thứ hai?",
    "options": [
      "A. Lựa chọn nhiễu 1",
      "B. Lựa chọn nhiễu 2",
      "C. Lựa chọn đúng",
      "D. Lựa chọn nhiễu 3"
    ],
    "correct_answer": 2,
    "explanation": "Giải thích chi tiết vì sao phương án C là chính xác..."
  }}
]

TÀI LIỆU NGUỒN:
{document}
"""
