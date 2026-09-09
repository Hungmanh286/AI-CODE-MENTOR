"""Prompts owned by the document-processing agent."""


class Prompts:
    # Trả về danh sách 10 câu hỏi với 3 mức độ: nhận biết/thông hiểu (dễ), vận dụng, vận dụng cao
    QUESTION_GENERATION_PROMPT = """
Bạn là chuyên gia biên soạn câu hỏi trắc nghiệm chuyên ngành công nghệ thông tin và khoa học máy tính.
Nhiệm vụ: Phân tích kỹ nội dung tài liệu nguồn và biên soạn bộ câu hỏi trắc nghiệm chất lượng cao, đòi hỏi tư duy logic, hiểu sâu bản chất và phản biện.

CÁC BƯỚC XÂY DỰNG:
1. Xác định các khái niệm, định nghĩa, cơ chế hoạt động cốt lõi trong tài liệu.
2. Phân tích mối quan hệ giữa các thành phần (so sánh, liên kết, ưu nhược điểm, luồng dữ liệu/thực thi).
3. Mỗi câu hỏi chỉ tập trung vào MỘT mục tiêu học tập rõ ràng, bám sát nội dung tài liệu.
4. Trích xuất chính xác "related_passage" (đoạn văn nguyên văn trong tài liệu nguồn hỗ trợ câu hỏi).

YÊU CẦU PHÂN BỔ ĐỘ KHÓ (TỔNG CỘNG 10 CÂU):
- 4 câu Dễ (Nhận biết / Thông hiểu): Khái niệm nền tảng, cú pháp cơ bản, thuật ngữ cốt lõi.
- 3 câu Vận dụng (Áp dụng): Phân tích ngữ cảnh, giải thích cơ chế, truy vết luồng xử lý hoặc đọc hiểu mã nguồn ngắn.
- 3 câu Vận dụng cao (Phân tích / Đánh giá): So sánh phương án, xử lý tình huống thực tế, tìm lỗi logic hoặc dự đoán kết quả thực thi phức tạp.

QUY TẮC NỘI DUNG:
- KHÔNG tạo câu hỏi dạng "Ý chính của đoạn văn là gì" hoặc "Theo tác giả trong đoạn trích...".
- Chỉ tạo nội dung câu hỏi, KHÔNG đính kèm đáp án trắc nghiệm tại bước này.
- Câu từ chuẩn mực, súc tích, không mơ hồ hay đa nghĩa.
- Đảm bảo các câu hỏi độc lập, không lặp lại nội dung của nhau.

ĐỊNH DẠNG ĐẦU RA BẮT BUỘC:
Trả về DUY NHẤT một mảng JSON (Raw JSON) theo cấu trúc:
[
  {{
    "question": "Nội dung câu hỏi trắc nghiệm?",
    "related_passage": "Đoạn trích nguyên văn từ tài liệu nguồn..."
  }}
]
Tuyệt đối không kèm văn bản giải thích ngoài JSON.

TÀI LIỆU NGUỒN:
{chunk}
"""

    QUESTION_REGENERATION_PROMPT = """
Bạn là chuyên gia biên soạn câu hỏi trắc nghiệm kỹ thuật chất lượng cao.
Nhiệm vụ: Tạo 5 câu hỏi mới rõ ràng, đúng trọng tâm, đạt chuẩn chất lượng dựa trên tài liệu nguồn bên dưới.

YÊU CẦU:
1. Phân tích các câu hỏi chưa đạt sau đây để rút kinh nghiệm và khắc phục triệt để nhược điểm:
{bad_qs}

2. Tuyệt đối KHÔNG trùng lặp hoặc tạo lại các câu hỏi đã đạt chuẩn sau:
{good_questions}

3. Tiêu chí câu hỏi mới:
   - Mỗi câu hỏi tập trung vào một khái niệm hoặc tình huống cụ thể, rõ ràng, giàu tính tư duy.
   - Không hỏi các câu chung chung như "Ý chính của đoạn trích" hoặc "Theo đoạn văn trên".
   - Có ít nhất 1-2 câu hỏi liên quan đến phân tích code hoặc áp dụng kỹ thuật thực tế.
   - Không sinh kèm đáp án lựa chọn; chỉ xuất nội dung câu hỏi.

ĐỊNH DẠNG ĐẦU RA:
- Trả về danh sách 5 câu hỏi mới, mỗi câu trên một dòng riêng biệt.
- Không đánh số thứ tự, không kèm văn bản giải thích.

TÀI LIỆU NGUỒN:
{chunk}
"""

    ANSWER_GENERATION_PROMPT = """
Bạn là chuyên gia thiết kế phương án trắc nghiệm cho bài tập kỹ thuật và lập trình.
Nhiệm vụ: Dựa vào danh sách câu hỏi và đoạn văn liên quan được cung cấp, hãy tạo 4 lựa chọn (A, B, C, D) cho từng câu hỏi.

YÊU CẦU THIẾT KẾ PHƯƠNG ÁN:
1. Mỗi câu hỏi gồm đúng 4 lựa chọn, bắt đầu bằng "A. ", "B. ", "C. ", "D. ".
2. Có duy nhất 1 đáp án chính xác tuyệt đối theo nội dung tài liệu.
3. Ba phương án nhiễu (distractors) phải:
   - Hợp lý, chặt chẽ, liên quan trực tiếp đến ngữ cảnh chuyên môn.
   - Phản ánh đúng những hiểu nhầm phổ biến, bẫy tư duy hoặc lỗi cú pháp/logic thường gặp của học viên.
   - Không chứa các lựa chọn ngô nghê, vô nghĩa hoặc dễ dàng bị loại trừ ngay lập tức.

QUY TẮC CỐT LÕI - CHỐNG THIÊN VỊ VỊ TRÍ ĐÁP ÁN (ANTI-BIAS):
- Đáp án đúng PHẢI ĐƯỢC PHÂN BỔ NGẪU NHIÊN VÀ CÂN BẰNG giữa 4 vị trí A, B, C, D trên toàn bộ tập câu hỏi.
- TUYỆT ĐỐI KHÔNG để tất cả hoặc đa số đáp án đúng dồn vào cùng một vị trí (ví dụ toàn A hoặc toàn B).
- Không tạo quy luật lặp tuần tự (A-B-C-D-A...).

ĐỊNH DẠNG ĐẦU RA BẮT BUỘC:
Trả về DUY NHẤT một JSON object theo đúng schema sau (không thêm backtick markdown hay giải thích):
{{
  "questions": [
    {{
      "id": 1,
      "question": "Nội dung câu hỏi?",
      "options": [
        "A. Phương án A",
        "B. Phương án B",
        "C. Phương án C",
        "D. Phương án D"
      ],
      "related_passage": "Đoạn văn nguyên văn giữ nguyên từ đầu vào"
    }}
  ]
}}

DANH SÁCH CÂU HỎI ĐẦU VÀO:
{questions}
"""

    EVALUATE_QA_PROMPT = """
Bạn là chuyên gia thẩm định và chuẩn hóa chất lượng đề thi trắc nghiệm chuyên ngành công nghệ thông tin.

NHIỆM VỤ THẨM ĐỊNH VÀ HIỆU CHỈNH:
- Bước 1: Đánh giá từng câu hỏi trong dữ liệu đầu vào dựa trên 3 tiêu chí (thang điểm 1-4):
  1. Mức độ nhận thức (score1): 4: Tư duy phân tích/tổng hợp sâu; 3: Vận dụng logic; 2: Ghi nhớ có hiểu; 1: Ghi nhớ máy móc.
  2. Độ rõ ràng & sư phạm (score2): 4: Diễn đạt chuẩn xác, không mơ hồ; 3: Khá rõ ràng; 2: Câu từ lủng củng; 1: Mơ hồ, sai ngữ nghĩa.
  3. Chất lượng phương án nhiễu (score3): 4: Nhiễu rất hợp lý, phân loại cao; 3: Nhiễu tốt; 2: Dễ đoán đáp án; 1: Nhiễu phi lý.
- Bước 2: Tính điểm trung bình: average_score = (score1 + score2 + score3) / 3.
- Bước 3: Phân loại:
  - "good": average_score >= 3.0
  - "bad": average_score < 3.0
- Bước 4: SỬA ĐỔI BẮT BUỘC: Đối với mỗi câu hỏi bị phân loại "bad", hãy viết lại câu hỏi và phương án để nâng cấp thành câu đạt chuẩn xuất sắc (gán average_score = 4.0).
- Bước 5: Xuất kết quả dưới dạng JSON hợp lệ duy nhất.

CẤU TRÚC JSON ĐẦU RA BẮT BUỘC:
{{
  "bad_questions": {{
    "0": [
      {{
        "question": "Nội dung câu hỏi chưa đạt",
        "average_score": 2.33
      }}
    ]
  }},
  "good_questions": {{
    "0": [
      "Nội dung câu hỏi tốt",
      "[ĐÃ SỬA] Nội dung câu hỏi đã được sửa đạt chuẩn"
    ]
  }},
  "good_question_answer": {{
    "0": [
      {{
        "id": 1,
        "question": "Nội dung câu hỏi tốt",
        "options": ["A. Lựa chọn 1", "B. Lựa chọn 2", "C. Lựa chọn 3", "D. Lựa chọn 4"],
        "average_score": 3.67
      }},
      {{
        "id": 2,
        "question": "[ĐÃ SỬA] Nội dung câu hỏi đã được sửa đạt chuẩn",
        "options": ["A. Lựa chọn 1", "B. Lựa chọn 2", "C. Lựa chọn 3", "D. Lựa chọn 4"],
        "average_score": 4.0
      }}
    ]
  }}
}}

YÊU CẦU:
- Đảm bảo JSON hợp lệ, đầy đủ cú pháp, các khóa là chuỗi số đại diện cho số thứ tự CHUNK ("0", "1", ...).
- Đánh giá toàn bộ câu hỏi trong dữ liệu, không bỏ sót bất kỳ câu nào.
- Chỉ xuất JSON hợp lệ, không kèm văn bản giải thích.

DỮ LIỆU ĐẦU VÀO:
{question_answers}
"""

    EVALUATE_AND_SELECT_PROMPT = """
Bạn là giảng viên chuyên môn phụ trách xây dựng và chọn lọc ngân hàng câu hỏi kiểm tra kỹ thuật.

NGỮ CẢNH ĐẦU VÀO:
- Dữ liệu câu hỏi được phân chia theo từng CHUNK (đánh số CHUNK 0, CHUNK 1, ...).
- Yêu cầu của người dùng: {query}
- Số lượng CHUNK: {num_chunks}
- Quy tắc số lượng: Chọn từ mỗi CHUNK một số lượng câu hỏi X = (Tổng số câu yêu cầu trong {query} chia cho {num_chunks}, làm tròn lên số nguyên gần nhất).

TIÊU CHÍ ƯU TIÊN TUYỂN CHỌN:
1. Điểm chất lượng cao: Ưu tiên các câu có average_score cao nhất.
2. Đúng mức độ khó: Phù hợp với yêu cầu về độ khó (easy/medium/hard) nếu có trong {query}.
3. Bao phủ chủ đề: Phù hợp nhất với trọng tâm kiến thức được đề cập.

ĐỊNH DẠNG ĐẦU RA BẮT BUỘC:
Trả về DUY NHẤT một JSON object theo cấu trúc:
{{
  "selected_questions": [
    {{
      "id": "chunk0_q1",
      "type": "multiple_choice",
      "difficulty": "easy",
      "question": "Nội dung câu hỏi được chọn?",
      "options": [
        "A. Phương án 1",
        "B. Phương án 2",
        "C. Phương án 3",
        "D. Phương án 4"
      ],
      "correct_answer": 0,
      "explanation": "Giải thích chi tiết tại sao đáp án đúng là chính xác và các lựa chọn khác chưa chuẩn."
    }}
  ]
}}

LƯU Ý:
- "difficulty" phải thuộc một trong ba mức: "easy", "medium", "hard".
- "correct_answer" là số nguyên từ 0 đến 3 (tương ứng A=0, B=1, C=2, D=3).
- Nếu dữ liệu đầu vào thiếu trường nào, hãy suy luận từ ngữ cảnh và điền đầy đủ.
- Tuyệt đối không thêm giải thích ngoài JSON.

DANH SÁCH CÂU HỎI ĐẦU VÀO THEO CHUNK:
{questions}
"""

    GENERATE_QUESTIONS_PROMPT = """
Bạn là chuyên gia sư phạm kỹ thuật số, phụ trách soạn thảo câu hỏi hỗ trợ người học nắm vững kiến thức.

NHIỆM VỤ:
Dựa trên tài liệu nguồn được cung cấp, hãy tạo câu hỏi trắc nghiệm bám sát yêu cầu sau của người dùng:
"{question}"

QUY TẮC BẮT BUỘC:
1. Bám sát 100% nội dung trong tài liệu nguồn, không đưa thông tin ngoài luồng.
2. Mỗi chủ đề/khái niệm chính tạo câu hỏi đa dạng mức độ (nhận biết, vận dụng, phân tích).
3. Đặt câu hỏi rõ ràng, gãy gọn, không dùng từ ngữ tối nghĩa.
4. Trả về danh sách câu hỏi trắc nghiệm, mỗi câu trên một dòng riêng biệt, không thêm lời dẫn giải thích.

TÀI LIỆU NGUỒN:
{documents}
"""
