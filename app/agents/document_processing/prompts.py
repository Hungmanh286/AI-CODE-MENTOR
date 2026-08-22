"""Prompts owned by the document-processing agent."""


class Prompts:
    # trả về danh sách 10 câu hỏi 3 mức độ : dễ, vận dụng, vận dụng cao
    QUESTION_GENERATION_PROMPT = """
Bạn là chuyên gia tạo câu hỏi trắc nghiệm cho môn lập trình hướng đối tượng bằng Java.
Hãy tạo câu hỏi trắc nghiệm đòi hỏi hiểu sâu, tư duy phản biện, và phân tích chi tiết dựa vào tài liệu nguồn bên dưới
Các câu hỏi không chỉ ghi nhớ thông tin đơn thuần, mà còn hướng đến các mức tư duy cao hơn như phân tích, tổng hợp, và đánh giá.

CÁC BƯỚC THỰC HIỆN:
1. Xác định các khái niệm hoặc thuật ngữ quan trọng trong tài liệu và hiểu rõ định nghĩa hoặc vai trò của chúng.
2. Xác định mối quan hệ giữa các khái niệm (so sánh, đối lập, liên kết, phụ thuộc) trong tài liệu nguồn.
3. Xác định các ví dụ hoặc ứng dụng được nhắc đến trong tài liệu.
4. Mỗi câu hỏi phải tập trung vào MỘT khái niệm duy nhất trong tài liệu nguồn bên dưới.

YÊU CẦU SỐ LƯỢNG CÂU HỎI : 4 câu dễ, 3 câu vận dụng, 3 câu vận dụng cao.

YÊU CẦU ĐẦU RA:
- Trả về danh sách JSON với cấu trúc: [{{"question": "câu hỏi", "related_passage": "đoạn văn liên quan"}}, ...]
- Không giải thích gì thêm.
- Mỗi câu hỏi phải độc lập, không trùng ý, không lặp ý.
- "related_passage" phải là đoạn văn nguyên văn từ tài liệu nguồn có liên quan trực tiếp đến câu hỏi.

LƯU Ý:
- Không dùng các cụm như "ý chính (main idea)" hoặc "đoạn văn (passages)" trong câu hỏi.
- Không liệt kê đáp án trắc nghiệm; chỉ trả về câu hỏi.
- Không sinh hai câu hỏi trong cùng một câu.
- Câu hỏi phải ngắn gọn, tập trung vào một khái niệm rõ ràng.
- Có 1–2 câu hỏi yêu cầu đọc hiểu hoặc phân tích code.
- Tất cả câu hỏi phải khác nhau và không bị trùng ý.

TÀI LIỆU NGUỒN:
{chunk}
"""

    QUESTION_REGENERATION_PROMPT = """
Bạn là chuyên gia biên soạn câu hỏi trắc nghiệm chất lượng cao.
Nhiệm vụ:
- Tạo 5 câu hỏi mới, rõ ràng, đúng trọng tâm, chất lượng cao.
- Dựa trên nhóm câu hỏi kém chất lượng sau và cải thiện chúng:
{bad_qs}

- Tuyệt đối không trùng lặp hoặc tạo lại các câu hỏi đã có:
{good_questions}

Yêu cầu bắt buộc:
- Chỉ trả về các câu hỏi, không kèm giải thích, không đánh số, không thêm bất kỳ văn bản nào ngoài câu hỏi.
- Mỗi câu hỏi phải tập trung vào một khái niệm duy nhất, ngắn gọn và dễ hiểu.
- Không hỏi những câu kiểu “ý chính (main idea)” hoặc “đoạn văn (passages)”.
- Không liệt kê đáp án trắc nghiệm.
- Trong tổng số câu hỏi, phải có 1–2 câu hỏi yêu cầu phân tích hoặc đọc hiểu code.
- Tất cả 5 câu hỏi phải hoàn toàn khác nhau và không trùng ý.

Tài liệu nguồn:
{chunk}
"""

    ANSWER_GENERATION_PROMPT = """
Bạn là chuyên gia tạo các lựa chọn trắc nghiệm cho môn lập trình dựa vào danh sách các câu hỏi và đoạn văn liên quan đến câu hỏi tương ứng bên dưới.
Hãy sinh ra các lựa chọn trắc nghiệm có 4 lựa chọn dựa vào danh sách câu hỏi và tài liệu bên dưới.

YÊU CẦU VỀ LỰA CHỌN:
- Mỗi câu hỏi có 4 lựa chọn, bắt đầu bằng: "A. ", "B. ", "C. ", "D. "
- Chỉ một lựa chọn đúng.
- Ba lựa chọn nhiễu (distractors) phải:
  • Phù hợp với ngữ cảnh.
  • Liên quan trực tiếp đế nội dung.
  • Phản ánh những hiểu lầm hoặc lỗi tư duy thường gặp, nhưng không được mâu thuẫn hoặc sai lệch hoàn toàn với nội dung.

**QUAN TRỌNG - TRÁNH BIAS VỊ TRÍ ĐÁP ÁN ĐÚNG:**
- ĐÁP ÁN ĐÚNG PHẢI ĐƯỢC PHÂN BỐ ĐỀU giữa các vị trí A, B, C, D
- TUYỆT ĐỐI KHÔNG đặt tất cả đáp án đúng ở cùng một vị trí (ví dụ: toàn A hoặc toàn B)
- Trong một tập câu hỏi, hãy đảm bảo:
  * Một số câu có đáp án đúng ở vị trí A
  * Một số câu có đáp án đúng ở vị trí B
  * Một số câu có đáp án đúng ở vị trí C
  * Một số câu có đáp án đúng ở vị trí D
- Không tạo pattern có quy luật (ví dụ: A, B, C, D, A, B, C, D...)
- Vị trí đáp án đúng phải NGẪU NHIÊN và CÂN BẰNG

YÊU CẦU VỀ FORMAT ĐẦU RA:
- TRẢ VỀ DUY NHẤT MỘT JSON OBJECT với cấu trúc: {{"questions": [...]}}
- Mỗi câu hỏi trong mảng questions phải có ĐẦY ĐỦ 4 TRƯỜNG:
  * id (integer): Số thứ tự của câu hỏi (1, 2, 3, ...)
  * question (string): Nội dung câu hỏi
  * options (array of strings): Mảng chứa 4 lựa chọn, mỗi lựa chọn BẮT ĐẦU bằng "A. ", "B. ", "C. ", "D. "
  * related_passage (string): Đoạn văn nguyên văn liên quan đến câu hỏi (GIỮ NGUYÊN từ đầu vào)

- KHÔNG ĐƯỢC THÊM markdown, backticks (```), giải thích hoặc bất kỳ văn bản nào ngoài JSON object.
- KHÔNG được thêm comments trong JSON.

VÍ DỤ FORMAT ĐẦU RA (CHÚ Ý: ĐÁP ÁN ĐÚNG Ở CÁC VỊ TRÍ KHÁC NHAU):
{{
  "questions": [
    {{
      "id": 1,
      "question": "Nội dung câu hỏi 1?",
      "options": [
        "A. Lựa chọn nhiễu 1",
        "B. Lựa chọn nhiễu 2",
        "C. Lựa chọn đúng",
        "D. Lựa chọn nhiễu 3"
      ],
      "related_passage": "Đoạn văn nguyên văn từ tài liệu..."
    }},
    {{
      "id": 2,
      "question": "Câu hỏi tiếp theo?",
      "options": [
        "A. Lựa chọn nhiễu 1",
        "B. Lựa chọn đúng",
        "C. Lựa chọn nhiễu 2",
        "D. Lựa chọn nhiễu 3"
      ],
      "related_passage": "Đoạn văn liên quan..."
    }},
    {{
      "id": 3,
      "question": "Câu hỏi thứ 3?",
      "options": [
        "A. Lựa chọn đúng",
        "B. Lựa chọn nhiễu 1",
        "C. Lựa chọn nhiễu 2",
        "D. Lựa chọn nhiễu 3"
      ],
      "related_passage": "Đoạn văn..."
    }}
  ]
}}

GIẢI THÍCH CÁC TRƯỜNG:
- question: Là nội dung câu hỏi từ danh sách đầu vào
- related_passage: Là đoạn văn liên quan đến câu hỏi đó (GIỮ NGUYÊN VĂN)

**NHẮC NHỞ QUAN TRỌNG:**
Trước khi trả về kết quả, hãy kiểm tra lại rằng đáp án đúng đã được phân bố đều giữa A, B, C, D. 
Nếu thấy nhiều câu đáp án đúng cùng ở một vị trí, hãy điều chỉnh lại.

CHỈ TRẢ VỀ JSON OBJECT — KHÔNG TRẢ VỀ BẤT KỲ THỨ GÌ KHÁC.

Danh sách câu hỏi:
{questions}
"""

    EVALUATE_QA_PROMPT = """
Bạn là chuyên gia thẩm định chất lượng câu hỏi trắc nghiệm cho lĩnh vực lập trình.

## NHIỆM VỤ ĐÁNH GIÁ VÀ CHỈNH SỬA:
- Bước 1: Đánh giá từng câu hỏi trong DỮ LIỆU ĐẦU VÀO dựa trên 3 TIÊU CHÍ (score1, score2, score3).
- Bước 2: Tính điểm trung bình (average_score = (score1 + score2 + score3) / 3).
- Bước 3: Phân loại good (average_score >= 3) hoặc bad (average_score < 3).
- Bước 4: **BẮT BUỘC SỬA**: Đối với các câu hỏi bad, hãy sửa thành câu hỏi good có chất lượng cao nhất. **Câu hỏi đã sửa phải đạt điểm tối đa (average_score = 4.0).**
- Bước 5: Trả về một JSON DUY NHẤT theo đúng CẤU TRÚC JSON ĐẦU RA.


## TIÊU CHÍ ĐÁNH GIÁ CHI TIẾT (1-4 điểm):
1. Mức độ hiểu biết: (4: chuyên sâu, tích hợp; 3: trực tiếp, ít tích hợp; 2: ghi nhớ + hiểu khái niệm; 1: ghi nhớ đơn thuần).
2. Mức độ rõ ràng: (4: hoàn toàn rõ; 3: đa phần rõ; 2: mơ hồ đáng kể; 1: rất khó hiểu).
3. Chất lượng lựa chọn: (4: nhiễu hợp lý, khó loại; 3: nhiễu tương đối; 2: dễ loại, 1 nhiễu; 1: nhiễu không liên quan).


## CẤU TRÚC JSON ĐẦU RA (BẮT BUỘC):
- PHÂN LOẠI: bad_questions: [question, average_score] của câu hỏi xấu. good_questions: [question] của câu hỏi tốt (bao gồm cả các câu đã sửa). good_question_answer: Chi tiết các câu hỏi tốt (id, question, options, correct_answer, explanation, average_score).
- CẤU TRÚC: {{"bad_questions":{{"0":[{{"question":,"average_score":}},{{"question":,"average_score":}}],"1":[], ...}},"good_questions":{{"0":["Câu hỏi tốt 1","Câu hỏi tốt 2","[ĐÃ SỬA] Câu hỏi bad đã sửa"],"1":[], ...}},"good_question_answer":{{"0":[{{"id":1,"question":"Câu hỏi tốt 1","options":["A","B","C","D"],"average_score":3.33}},{{"id":2,"question":"[ĐÃ SỬA] Câu hỏi bad đã sửa","options":["A","B","C","D"],"average_score":4.0}}],"1":[], ...}}}}


## YÊU CẦU BẮT BUỘC:
1. CHỈ TRẢ VỀ MỘT JSON HỢP LỆ TRÊN MỘT DÒNG DUY NHẤT.
2. JSON phải tuân thủ cấu trúc trên với 3 key.
3. Đánh giá hết tất cả câu hỏi, không được bỏ qua. Câu hỏi khó đánh giá mặc định điểm thấp.


## MÔ TẢ DỮ LIỆU ĐẦU VÀO:
1. Dữ liệu được trình bày dưới dạng TEXT đã được format sẵn.
2. Mỗi CHUNK được bắt đầu bằng "CHUNK X" (với X là số chunk).
3. Trong mỗi CHUNK có nhiều câu hỏi, mỗi câu hỏi có format:
   - "CÂU HỎI Y:" (đánh số từ 1)
   - "Nội dung: [nội dung câu hỏi]" 
   - "Đáp án:" (4 lựa chọn A, B, C, D)
   - "Đoạn văn liên quan: [đoạn văn nguyên văn từ tài liệu]"
4. Bạn cần đánh giá từng câu hỏi dựa trên nội dung, đáp án và đoạn văn liên quan.


DỮ LIỆU ĐẦU VÀO:
{question_answers}
"""

    EVALUATE_AND_SELECT_PROMPT = """
Bạn là một giảng viên chuyên môn về lập trình.

GIẢI THÍCH DỮ LIỆU ĐẦU VÀO:
- Dữ liệu đầu vào bao gồm nhiều CHUNK.
- MỖI CHUNK chứa một danh sách câu hỏi (mỗi câu hỏi có thể có các trường như id, question, options, average_score...).
- CHUNK được đánh số CHUNK 0, CHUNK 1, CHUNK 2, ... và mỗi chunk hoạt động như một "tập con" của toàn bộ dữ liệu.
- Nhiệm vụ của bạn là chọn ra đúng số lượng câu hỏi từ MỖI CHUNK dựa trên yêu cầu:
Yêu cầu của người dùng : {query}
Công thức tính số lượng câu hỏi cần chọn từ MỖI CHUNK: **Tổng số câu hỏi yêu cầu (số bên trong {query}) chia cho {num_chunks}** (Lưu ý: PHẢI LÀM TRÒN KẾT QUẢ PHÉP CHIA NÀY LÊN số nguyên gần nhất).

CÁC BƯỚC THỰC HIỆN: 
Bước 1 : **Xác định số lượng (X) câu hỏi cần chọn** bằng cách áp dụng công thức trên (TỔNG CÂU / {num_chunks}, làm tròn lên). Sau đó, chọn ra chính xác **X** câu hỏi từ mỗi CHUNK từ danh sách câu hỏi trong CHUNK đó.
Bước 2 : **Ưu tiên chọn** các câu hỏi theo thứ tự: 1) **average_score cao hơn** (chất lượng); 2) **phù hợp nhất với MỨC ĐỘ KHÓ** (nếu được đề cập trong {query}); và 3) **phù hợp nhất với chủ đề** trong {query}.
Bước 3 : Trả về một JSON object với key "selected_questions" chứa mảng các câu hỏi đã chọn từ MỖI CHUNK.

---
## MÔ TẢ CẤU TRÚC DỮ LIỆU ĐẦU VÀO :
1. Dữ liệu là một **Dictionary** lớn, nơi **MỖI KEY** là một chuỗi số ("0", "1", "2", ...) đại diện cho một CHUNK.
2. **MỖI VALUE** là một danh sách (list) các đối tượng JSON (câu hỏi).
3. Mỗi câu hỏi đã được đánh giá và chứa tối thiểu các trường: **id**, **question**, **options**, và **average_score** (điểm chất lượng).
---

DANH SÁCH CÂU HỎI ĐẦU VÀO (THEO TỪNG CHUNK):
{questions}

---
YÊU CẦU BẮT BUỘC VỀ FORMAT ĐẦU RA:
- TRẢ VỀ DUY NHẤT MỘT JSON OBJECT HỢP LỆ với cấu trúc: {{"selected_questions": [...]}}
- Mỗi câu hỏi trong selected_questions phải có ĐẦY ĐỦ 7 TRƯỜNG BẮT BUỘC:
  * id (string): ID duy nhất của câu hỏi (ví dụ: "q1", "q2", "chunk0_q1", ...)
  * type (string): Loại câu hỏi, phải là "multiple_choice"
  * difficulty (string): Mức độ khó, phải là một trong: "easy", "medium", "hard"
  * question (string): Nội dung câu hỏi
  * options (array of strings): Mảng chứa 4 lựa chọn (A, B, C, D), mỗi lựa chọn bắt đầu bằng "A. ", "B. ", "C. ", "D. "
  * correct_answer (integer): CHỈ SỐ INTEGER từ 0 đến 3, tương ứng với A=0, B=1, C=2, D=3
  * explanation (string): Giải thích chi tiết tại sao đáp án này là đúng

- Nếu một số trường thông tin bị thiếu trong dữ liệu đầu vào (ví dụ: type, difficulty, correct_answer, explanation), 
  bạn phải tự xác định và điền đầy đủ các trường đó dựa trên ngữ cảnh câu hỏi.
  
- KHÔNG ĐƯỢC THÊM markdown, backticks, giải thích hoặc bất kỳ văn bản nào ngoài JSON object.
- KHÔNG được thêm comments (//) trong JSON.

VÍ DỤ FORMAT ĐẦU RA MONG MUỐN:
{{
  "selected_questions": [
    {{
      "id": "q1",
      "type": "multiple_choice",
      "difficulty": "easy",
      "question": "Câu hỏi mẫu?",
      "options": ["A. Đáp án 1", "B. Đáp án 2", "C. Đáp án 3", "D. Đáp án 4"],
      "correct_answer": 0,
      "explanation": "Giải thích chi tiết..."
    }}
  ]
}}

CHỈ TRẢ VỀ JSON OBJECT — KHÔNG TRẢ VỀ BẤT KỲ THỨ GÌ KHÁC.
"""

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
