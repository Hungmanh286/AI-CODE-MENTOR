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
Bạn là chuyên gia tạo câu hỏi giúp người dùng hiểu nội dung trong Tài liệu nguồn bên dưới.

Hãy tạo câu hỏi bao gồm 10 câu hỏi chất lượng cao

Lưu ý:
- Chỉ liệt kê các câu hỏi, không giải thích, không thêm định dạng hoặc số thứ tự, không thêm văn bản nào ngoài câu hỏi.

Tài liệu nguồn:
{chunk}
"""

    QUESTION_REGENERATION_PROMPT = """
Bạn là chuyên gia cải thiện câu hỏi
Câu hỏi cần cải thiện: {bad_qs}

Hãy tạo lại câu hỏi tốt hơn cho tài liệu sau đây, tránh lặp lại câu hỏi đã có: {good_questions}

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
Hãy sinh ra các câu trả lời dựa vào tài liệu bên dưới.

Danh sách câu hỏi: 
{questions}

tài liệu : 
{chunk}
Lưu ý trả về danh sách câu hỏi và câu trả lời dưới dạng các JSON với cấu trúc sau:
{{
    "id": <số nguyên>,
    "question": "<nội dung câu hỏi>",
    "answer": "<nội dung câu trả lời>",
    "explanation": "<giải thích (nếu có)>"
  }},
"""
    # thêm 1 trường là good question
    EVALUATE_QA_PROMPT = """
Bạn là chuyên gia đánh giá câu hỏi sinh ra từ tài liệu.

Nhiệm vụ:
Đánh giá toàn bộ danh sách các cặp câu hỏi - đáp án dưới đây, được chia theo từng chunk_index.

Mục tiêu:
Phân loại từng câu hỏi thành hai nhóm:
- **good_question_answer**: câu hỏi đạt tiêu chí chất lượng (chính xác, phù hợp, đầy đủ, có giá trị sư phạm)
- **bad_questions**: câu hỏi chưa đạt (sai lệch, mơ hồ, quá đơn giản hoặc không phản ánh nội dung chunk)

Ngoài ra, hãy tạo thêm một JSON phụ **good_questions** chỉ chứa phần nội dung câu hỏi (text) của các câu hỏi tốt.

Tiêu chí đánh giá:
1. **Độ chính xác**: phản ánh đúng nội dung tài liệu.
2. **Độ đầy đủ**: bao quát đủ ý chính, không rời rạc.
3. **Mức độ phù hợp**: đúng ngữ cảnh, độ khó hợp lý.
4. **Tính sư phạm**: giúp người học hiểu và ghi nhớ kiến thức tốt hơn.

Yêu cầu đầu ra:
Trả về **duy nhất một JSON hợp lệ**, KHÔNG kèm bất kỳ mô tả hay ký tự ngoài nào.

Cấu trúc JSON bắt buộc:
{{
  "bad_questions": {{
      "<chunk_index>": [
          "<nội dung câu hỏi 1>",
          "<nội dung câu hỏi 2>",
          ...
      ],
      ...
  }},
  "good_questions": {{
      "<chunk_index>": [
          "<nội dung câu hỏi 1>",
          "<nội dung câu hỏi 2>",
          ...
      ],
      ...
  }},
  "bad_questions": {{
      "<chunk_index>": [
          "<nội dung câu hỏi 1>",
          "<nội dung câu hỏi 2>",
          ...
      ],
      ...
  }},
"good_question_answer": {{
    "<chunk_index>": [
        {{
            "id": <số nguyên>,
            "question": "<nội dung câu hỏi>",
            "answer": "<nội dung câu trả lời>",
            "explanation": "<giải thích (nếu có)>"
        }}
    ],
    ...
  }},
}}

Hướng dẫn bắt buộc:
- `chunk_index` phải trùng với dữ liệu đầu vào (kiểu số nguyên).
- Nếu chunk không có câu hỏi tốt hoặc xấu, vẫn phải có key đó với list rỗng `[]`.
- **good_question_answer**: giữ nguyên toàn bộ cấu trúc gốc (id, choices, correct, explanation, v.v.).
- **good_questions**: chỉ chứa phần text của các câu hỏi tốt.
- **bad_questions**: chỉ liệt kê nội dung câu hỏi dạng text.
- Không được viết lại, paraphrase hay thêm bình luận.
- Tuyệt đối **chỉ trả về JSON thuần túy**, không bao gồm markdown hoặc ký tự ```.

Dữ liệu đầu vào (danh sách cặp câu hỏi-đáp án theo chunk):
{question_answers}
"""

    EVALUATE_QUESTIONS_PROMPT = """
Bạn là một giảng viên có chuyên môn trong lĩnh vực lập trình hướng đối tượng.

Danh sách câu hỏi và câu trả lời cần đánh giá:
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

    # Modules for summarization
    EXTRACTIVE_SUMMARIZE_PROMPT = """
Bạn là một mô hình tóm tắt trích chọn (extractive summarizer) có khả năng đánh giá mức độ quan trọng của từng câu dựa trên ngữ cảnh và ý nghĩa thông tin.

Bên dưới là một phần của tài liệu:
{document}

Hãy thực hiện các bước sau:

1. **Chấm điểm quan trọng** cho từng câu trong tài liệu dựa trên:
   - Mức độ chứa đựng thông tin trung tâm, kết luận hoặc phát hiện chính.
   - Sự liên kết với chủ đề tổng thể của tài liệu.
   - Mức độ độc lập và tự chứa (câu có thể hiểu mà không cần tham chiếu ra ngoài).

2. **Chọn ra các câu nổi bật nhất** (khoảng 5–10 câu hoặc ít hơn nếu văn bản ngắn),
   ưu tiên các câu có điểm quan trọng cao nhất, thể hiện được toàn bộ nội dung cốt lõi.

3. **Giữ nguyên nội dung gốc của các câu** (không viết lại, không diễn giải, không tóm gọn).

4. **Chỉ xuất ra danh sách các câu được chọn**, mỗi câu trên một dòng, theo đúng thứ tự xuất hiện trong tài liệu gốc.

Đầu ra cuối cùng là tập hợp các câu quan trọng nhất của tài liệu.
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
