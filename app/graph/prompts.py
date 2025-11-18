class Prompts:
    """Class Prompt templates."""

    # Modules for question answer generation
    SUMMARIZE_CHUNK_SUMMARY_PROMPT = """
Bên dưới là một tài liệu:
{document}

Hãy viết một bản tóm tắt bao gồm toàn bộ các thông tin chính.
Trong phần tóm tắt, không được nhắc đến các từ như “tài liệu” hoặc “bản tóm tắt”.
    """

    QUESTION_GENERATION_PROMPT = """
Bạn là chuyên gia tạo câu hỏi trắc nghiệm cho môn lập trình hướng đối tượng bằng java.

LƯU Ý:
- Không sử dụng các cụm như “ý chính (main idea)” hoặc “đoạn văn (passages)” trong câu hỏi.
- Không liệt kê đáp án trắc nghiệm. Chỉ trả về câu hỏi.
- Không sinh nhiều hơn một câu hỏi trong cùng một câu.
- Câu hỏi chỉ nên tập trung vào một khái niệm rõ ràng và không quá dài.
- 10 câu hỏi phải khác nhau và không bị trùng ý.

CÁC BƯỚC THỰC HIỆN : 
1. Xác định các khái niệm hoặc thuật ngữ quan trọng trong tài liệu, và hiểu rõ định nghĩa hoặc vai trò của chúng trong tài liệu nguồn bên dưới
2. Xác định mối quan hệ giữa các khái niệm (so sánh, đối lập, liên kết, phụ thuộc) trong tài liệu nguồn bên dưới
3. Xác định các ví dụ hoặc ứng dụng được nhắc đến trong tài liệu nguồn bên dưới 
4. Hãy tạo 10 câu hỏi trắc nghiệm về lập trình hướng đối tượng Java, mỗi câu tập trung vào MỘT khái niệm duy nhất từ tài liệu dưới đây.
Yêu cầu tư duy bậc cao cho 10 câu hỏi, bao gồm :
- 4 câu: Phân tích (Analysis) – so sánh, tìm lỗi, giải thích hành vi  
- 3 câu: Tổng hợp (Synthesis) – thiết kế, mở rộng, kết hợp  
- 3 câu: Đánh giá (Evaluation) – chọn giải pháp tối ưu, đánh giá 
5. Trả về danh sách các câu hỏi : [câu hỏi 1, câu hỏi 2, ...] không phải giải thích gì thêm
 
Tài liệu nguồn:
{chunk}
"""

    QUESTION_REGENERATION_PROMPT = """
Bạn là chuyên gia cải thiện câu hỏi
Câu hỏi cần cải thiện: 
{bad_qs}

Hãy tạo lại câu hỏi tốt hơn cho tài liệu sau đây, tránh lặp lại câu hỏi đã có: 
{good_questions}

Yêu cầu:
- Chỉ liệt kê các câu hỏi, không giải thích, không thêm định dạng hoặc số thứ tự, không thêm văn bản nào ngoài câu hỏi.

Tài liệu nguồn:
{chunk}

"""

    #     QUESTION_extractor_PROMPT = """
    # xử lý câu hỏi các câu hỏi, loại bỏ trùng lặp, đảm bảo chỉ giữ lại
    # các câu hỏi liên quan, đa dạng và không dư thừa.
    # {good_questions}
    # """

    ANSWER_GENERATION_PROMPT = """
Bạn là chuyên gia tạo các lựa chọn trắc nghiệm cho môn lập trình hướng đối tượng bằng java.
Hãy sinh ra các lựa chọn trắc nghiệm dạng có 4 lựa chọn lựa chọn dựa vào danh sách câu hỏi và tài liệu bên dưới.

Yêu cầu:
- Mỗi câu hỏi có 4 lựa chọn lựa chọn, bắt đầu bằng: A., B., C., D.
- Chỉ một lựa chọn đúng.
- Ba lựa chọn nhiễu (distractors) phải:
  • Phù hợp với ngữ cảnh.
  • Liên quan trực tiếp đến nội dung.
  • Phản ánh những hiểu lầm hoặc lỗi tư duy thường gặp, nhưng không được mâu thuẫn hoặc sai lệch hoàn toàn với nội dung.

Lưu ý:
Trả về danh sách câu hỏi và câu trả lời dưới dạng các JSON với cấu trúc sau:
[
  {{
    "id": <số nguyên>,
    "question": "<nội dung câu hỏi>",
    "options": [
        "<lựa chọn A>",
        "<lựa chọn B>",
        "<lựa chọn C>",
        "<lựa chọn D>"
    ],
  }},
  ...
]

Danh sách câu hỏi:\n
{questions}

Tài liệu:\n
{chunk}

"""

    EVALUATE_QA_PROMPT = """
Bạn là một chuyên gia đánh giá chất lượng câu hỏi trắc nghiệm cho môn lập trình hướng đối tượng.

NHIỆM VỤ:
- Bước 1: Đánh giá từng câu hỏi trong DỮ LIỆU ĐẦU VÀO dựa trên 3 tiêu chí bên dưới.
- Bước 2: Tính điểm trung bình cho mỗi câu hỏi (average_score = (score1 + score2 + score3) / 3).
- Bước 3: Phân loại câu hỏi thành good (average_score >= 3) hoặc bad (average_score < 3).
- Bước 4: Trả về một JSON duy nhất theo đúng CẤU TRÚC JSON ĐẦU RA.

TIÊU CHÍ ĐÁNH GIÁ CHI TIẾT:

1. Mức độ hiểu biết (1-4 điểm):
   -Điểm 4: Kiểm tra hiểu biết chuyên sâu, yêu cầu tích hợp và vận dụng nhiều ý tưởng.
   -Điểm 3: Kiểm tra hiểu biết nhưng theo cách trực tiếp, ít cần tích hợp.
   -Điểm 2: Chủ yếu dựa vào ghi nhớ nhưng vẫn có chút yêu cầu hiểu khái niệm.
   -Điểm 1: Chỉ kiểm tra ghi nhớ đơn thuần.

2. Mức độ rõ ràng (1-4 điểm):
   -Điểm 4: Hoàn toàn rõ ràng, không có mơ hồ.
   -Điểm 3: Đa phần rõ ràng nhưng có vài điểm hơi mơ hồ.
   -Điểm 2: Có mơ hồ đáng kể, dễ gây nhầm lẫn.
   -Điểm 1: Rất khó hiểu hoặc không rõ.

3. Chất lượng lựa chọn (1-4 điểm):
   -Điểm 4: Các lựa chọn nhiễu hợp lý, liên quan, gây khó loại trừ.
   -Điểm 3: Lựa chọn nhiễu tương đối tốt nhưng chưa tinh vi.
   -Điểm 2: Hầu hết dễ loại trừ, chỉ có 1 nhiễu hợp lý.
   -Điểm 1: Nhiễu rất dễ loại bỏ hoặc không liên quan.

PHÂN LOẠI:
- bad_questions: Chỉ chứa nội dung text của các câu hỏi xấu (điểm trung bình < 3).
- good_questions: Chỉ chứa nội dung text của các câu hỏi tốt (điểm >= 3).
- good_question_answer: Các câu hỏi tốt với đầy đủ thông tin (id, question, options, correct_answer, explanation).

CẤU TRÚC JSON ĐẦU RA (BẮT BUỘC):
{{"bad_questions":{{"0":[{{"question":"Câu hỏi xấu 1","average_score":2.33}},{{"question":"Câu hỏi xấu 2","average_score":1.67}}],"1":[], ...}},"good_questions":{{"0":["Câu hỏi tốt 1","Câu hỏi tốt 2"],"1":[], ...}},"good_question_answer":{{"0":[{{"id":1,"question":"Câu hỏi tốt 1","options":["A","B","C","D"],"average_score":3.33}},{{"id":2,"question":"Câu hỏi tốt 2","options":["A","B","C","D"],"average_score":3.67}}],"1":[], ...}}}}

GIẢI THÍCH :
chunk_index là chỉ số của chunk trong tài liệu gốc (có trong dòng đầu trong mỗi danh sách câu hỏi từ dữ liệu đầu vào)
YÊU CẦU BẮT BUỘC:
1. CHỈ TRẢ VỀ MỘT JSON HỢP LỆ TRÊN MỘT DÒNG DUY NHẤT. Không có văn bản, giải thích, hay markdown khác.
2. JSON phải tuân thủ cấu trúc trên với 3 key: bad_questions, good_questions, good_question_answer.
3. Mỗi key phải chứa dict với chunk_index là string (ví dụ: "0", "1", "2").
4. Nếu một chunk không có câu hỏi tốt hoặc xấu, trả về danh sách rỗng [] cho chunk đó.
5. Tất cả chunk_index từ đầu vào phải xuất hiện trong cả 3 key của JSON đầu ra.

DỮ LIỆU ĐẦU VÀO:
{question_answers}
"""

    EVALUATE_AND_SELECT_PROMPT = """
Bạn là một giảng viên chuyên môn về lập trình hướng đối tượng.

### NHIỆM VỤ:
- Bước 1: Đánh giá (nội bộ) từng câu hỏi trong DỮ LIỆU ĐẦU VÀO dựa trên 2 TIÊU CHÍ ĐÁNH GIÁ (Bloom và Hấp dẫn).
- Bước 2: Đối với MỖI CHUNK, thực hiện "QUY TRÌNH CHỌN LỌC" bên dưới để tạo ra một danh sách các câu hỏi được chọn cho chunk đó.
- Bước 3: Trả về một JSON duy nhất theo đúng CẤU TRÚC JSON ĐẦU RA.

### TIÊU CHÍ ĐÁNH GIÁ CHI TIẾT (Thang 1-4):

1.  **Mức độ nhận thức (Bloom’s Taxonomy):**
    * 4: yêu cầu tư duy bậc cao (phân tích, tổng hợp, đánh giá)
    * 3: yêu cầu vận dụng hoặc hiểu khái niệm
    * 2: yêu cầu hiểu cơ bản hoặc ghi nhớ có ý nghĩa
    * 1: chỉ yêu cầu ghi nhớ máy móc

2.  **Mức độ hấp dẫn (Engagement Level):**
    * 4: rất hấp dẫn, kích thích tư duy
    * 3: hấp dẫn nhưng không thật sự độc đáo
    * 2: tương đối hấp dẫn nhưng đơn giản
    * 1: không thú vị, ít hấp dẫn

### QUY TRÌNH CHỌN LỌC (Áp dụng cho từng chunk độc lập):
Bạn phải chọn một tập hợp câu hỏi từ mỗi chunk đáp ứng **ĐỒNG THỜI** 2 điều kiện:

1.  **Điều kiện Điểm hấp dẫn:** CHỈ bao gồm các câu hỏi có `engagement_score` >= 2.
2.  **Điều kiện Độ phủ nhận thức:** Tập hợp được chọn PHẢI chứa **ít nhất một (1) câu hỏi** cho **MỖI MỨC** `cognitive_score` (tức là ít nhất một câu điểm 1, một câu điểm 2, một câu điểm 3, VÀ một câu điểm 4).

**QUY TẮC XỬ LÝ (cho mỗi chunk):**
- Bước A (Nội bộ): Đánh giá tất cả câu hỏi trong chunk.
- Bước B (Nội bộ): Lọc ra "danh sách ứng viên" của chunk (câu có `engagement_score >= 2`).
- Bước C (Lựa chọn): Từ "danh sách ứng viên", chọn một tập hợp cuối cùng đảm bảo độ phủ nhận thức (1, 2, 3, 4).
- Bước D (Trả về): Trả về tập hợp ở Bước C.
- **Nếu không thể** tạo được một danh sách đáp ứng cả hai điều kiện cho một chunk (ví dụ: chunk "0" không có câu `cognitive_score = 4` nào đạt `engagement_score >= 2`), hãy trả về một danh sách rỗng `[]` cho chunk đó.

### Cấu trúc dữ liệu đầu ra:
Bạn phải trả về **duy nhất một danh sách JSON hợp lệ** (`[...]`) gồm các object đại diện cho từng câu hỏi **ĐÃ ĐƯỢC CHỌN LỌC**, với đầy đủ các trường:

1. "id": mã định danh duy nhất (ví dụ: "q1")
2. "type": loại câu hỏi (ví dụ: "multiple_choice")
3. "difficulty": mức độ khó
4. "question": nội dung câu hỏi
5. "options": danh sách 4 lựa chọn A/B/C/D
6. "correct_answer": chỉ số (0–3) của đáp án đúng trong "options"
7. "explanation": giải thích ngắn gọn cho đáp án đúng
8. **"cognitive_score"**: điểm Bloom (1–4)
9. **"engagement_score"**: điểm hấp dẫn (1–4)

### Ví dụ đúng chuẩn (Ví dụ này minh họa cấu trúc, kết quả thực tế phải tuân thủ Mục 3):
[{{"id":"q1","type":"multiple_choice","difficulty":"medium","question":"Tính đóng gói là gì?","options":["A","B","C","D"],"correct_answer":0,"explanation":"Giải thích","cognitive_score":2,"engagement_score":2}}]


### Yêu cầu bắt buộc:
- Trả về **chính xác một danh sách JSON hợp lệ** (có thể là danh sách rỗng `[]` nếu không đáp ứng điều kiện).
- **Không** thêm mô tả, markdown, nhận xét hay bất kỳ văn bản nào ngoài JSON.
- Mỗi object phải bao gồm đầy đủ các trường được liệt kê.

Danh sách câu hỏi :
{questions}
"""
    # Modules for summarization
    EXTRACTIVE_SUMMARIZE_PROMPT = """
Bạn là chuyên gia tóm tắt trích xuất.

Nhiệm vụ của bạn là tạo bản tóm tắt trích xuất cho chunk bên dưới 
Tóm tắt trích xuất phải:
• Chỉ chọn ra các câu xuất hiện nguyên văn trong chunk.
• Không được viết lại, paraphrase, hoặc gộp câu.
• Chỉ chọn các câu quan trọng nhất thể hiện ý chính.
• Loại bỏ trùng lặp.

HƯỚNG DẪN:
1. Xác định các câu quan trọng nhất thể hiện nội dung chính.
2. Sao chép nguyên văn các câu này đúng như trong chunk.
3. Trả về danh sách câu tóm tắt theo đúng thứ tự trong văn bản.

ĐỊNH DẠNG TRẢ VỀ:
Trả về bản tóm tắt trích xuất dưới dạng danh sách các câu, mỗi câu trên một dòng.
Không giải thích gì thêm.

Chunk: 
{chunk_text}

"""

    SUMMARIZE_CHUNK_SUMMARY_CIATATIONS_PROMPT = """
Bên dưới là một tài liệu trong đó mỗi đoạn văn được gán một nhãn ở cuối ([n]) và được ngăn cách bằng dấu xuống dòng:
{document}

Hãy viết một bản tóm tắt bao gồm toàn bộ các thông tin chính.
Trong phần tóm tắt, không được nhắc đến các từ như “tài liệu” hoặc “bản tóm tắt”.
Sau mỗi câu trong bản tóm tắt, bạn cần gán nhãn cho câu đó để thể hiện nó tương ứng với đoạn văn nào trong tài liệu.
Cụ thể, hãy tuân theo định dạng sau:
<câu 1>. [n] <câu 2>. [m] ...
"""

    SUMMARIZE_CHUNK_SUMMARY_Extract_PROMPT = """
Bên dưới là một tài liệu :
{document}  
"""
    # Merge normal phân cấp
    HMerge_SUMMARY_PROMPT = """
Bên dưới là nhiều bản tóm tắt của các phần khác nhau trong một tài liệu:
{very_document}

Hãy gộp các bản tóm tắt đã cho thành một bản tóm tắt duy nhất bao gồm toàn bộ các thông tin chính.
Trong phần tóm tắt, không được nhắc đến các từ như “tài liệu” hoặc “bản tóm tắt”.
"""
    # Merge với trích dẫn
    HMerge_SUMMARY_Citations_PROMPT = """
Bên dưới là nhiều bản tóm tắt của các phần khác nhau trong một tài liệu, trong đó mỗi câu trong bản tóm tắt đều có nhãn ở cuối ([1], [2], …) và được ngăn cách bằng dấu xuống dòng:
{document}

Hãy gộp các bản tóm tắt đã cho thành một bản tóm tắt duy nhất bao gồm toàn bộ các thông tin chính.
Trong phần tóm tắt, không được nhắc đến các từ như “tài liệu” hoặc “bản tóm tắt”.
Sau mỗi câu trong bản tóm tắt, bạn cần gán nhãn cho câu đó để thể hiện nó tương ứng với đoạn văn nào trong tài liệu gốc.
Cụ thể, hãy tuân theo định dạng sau:
<câu 1>. [n] <câu 2>. [m] ...
"""
    # merge với ngữ cảnh hỗ trợ
    Extract_Retrieve_Support_PROMPT = """
Bên dưới là nhiều bản tóm tắt của các phần khác nhau trong một tài liệu:
{document}
Bên dưới là các ngữ cảnh hỗ trợ tương ứng với những bản tóm tắt đã cho ở trên:
{context}

Hãy gộp các bản tóm tắt đã cho thành một bản tóm tắt duy nhất bao gồm toàn bộ các thông tin chính,
và sử dụng các ngữ cảnh hỗ trợ để đảm bảo rằng bản tóm tắt gộp không chứa sai lệch về mặt nội dung.
Phần nội dung chính của bản tóm tắt phải dựa hoàn toàn trên các bản tóm tắt đã cho,
trong khi các ngữ cảnh hỗ trợ chỉ được dùng để kiểm chứng tính chính xác.
Trong phần tóm tắt, không được nhắc đến các từ như “tài liệu”, “ngữ cảnh” hoặc “bản tóm tắt”.
    """

    # merge với ngữ cảnh hỗ trợ có trích dẫn
    Cite_Support_PROMPT = """
Bên dưới là nhiều bản tóm tắt của các phần khác nhau trong một tài liệu:
{document}
Bên dưới là các ngữ cảnh hỗ trợ tương ứng với những bản tóm tắt đã cho ở trên, trong đó mỗi ngữ cảnh được gán một nhãn ở cuối ([n]) và được ngăn cách bằng dấu xuống dòng:
{context}

Hãy gộp các bản tóm tắt đã cho thành một bản tóm tắt duy nhất bao gồm toàn bộ các thông tin chính, đồng thời sử dụng các ngữ cảnh hỗ trợ để đảm bảo rằng bản tóm tắt gộp không chứa sai lệch về mặt nội dung.
Phần nội dung chính của bản tóm tắt phải dựa hoàn toàn trên các bản tóm tắt đã cho, trong khi các ngữ cảnh hỗ trợ chỉ được dùng để kiểm chứng tính chính xác.
Trong phần tóm tắt, không được nhắc đến các từ như “tài liệu”, “ngữ cảnh” hoặc “bản tóm tắt”.
Sau mỗi câu trong bản tóm tắt, bạn cần gán nhãn cho câu đó để thể hiện nó tương ứng với ngữ cảnh hỗ trợ nào.
Cụ thể, hãy tuân theo định dạng sau:
<câu 1>. [n] <câu 2>. [m] ...
    """

    SUMMARIZE_PROMPT = """Bạn là một trợ lý AI giúp tóm tắt nội dung tài liệu dài thành các đoạn ngắn gọn.
    Hãy tóm tắt đoạn văn sau bằng tiếng Việt, giữ lại thông tin quan trọng:
    ---{text}
    ---Tóm tắt:
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

    FEEDBACK_QUESTIONS_PROMPT = """
Bạn là chuyên gia giải thích và trả lời chi tiết cho câu hỏi sau:  
"{question}"

Dựa hoàn toàn vào nội dung của **Tài liệu nguồn** bên dưới.  
Hãy đảm bảo rằng câu trả lời:
- Giải thích rõ ràng, chính xác, có logic.  
- Dẫn chứng cụ thể từ tài liệu khi cần thiết.  
- Không đưa ra thông tin ngoài tài liệu.

**Tài liệu nguồn:**  
{documents}
"""
