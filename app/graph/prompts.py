class Prompts:
    """Class Prompt templates."""

    # Modules for question answer generation
    SUMMARIZE_CHUNK_SUMMARY_PROMPT = """
Bên dưới là một tài liệu:
{document}

Hãy viết một bản tóm tắt bao gồm toàn bộ các thông tin chính.
Trong phần tóm tắt, không được nhắc đến các từ như “tài liệu” hoặc “bản tóm tắt”.
    """

    MIND_MAP_PROMPT = """
Bạn là một AI chuyên biệt trong việc tạo ra sơ đồ tư duy (mind map) bằng hình ảnh.
Mục tiêu là tạo ra một hình ảnh sơ đồ tư duy (mind map) TRỰC QUAN, RÕ RÀNG và ĐỘ CHÍNH XÁC CAO về mặt văn bản, dựa trên tài liệu được cung cấp.

Yêu cầu về Hình ảnh và Nội dung:
1.  **Chủ đề:** Tạo một sơ đồ tư duy hình ảnh về nội dung được cung cấp trong Tài liệu nguồn.
2.  **Phong cách Hình ảnh:**
    * **Hiện đại & Tối giản:** Thiết kế theo phong cách phẳng (flat design), sử dụng các đường nét sạch sẽ và không quá nhiều chi tiết trang trí.
    * **Tông màu:** Sử dụng tông màu sáng, tươi mới (ví dụ: pastel hoặc màu sắc nhẹ nhàng), có độ tương phản cao để dễ đọc. Nền màu trắng hoặc rất nhạt.
    * **Bố cục:** Bố cục rõ ràng, cân đối, dễ nhìn. Các nhánh phát triển từ trung tâm ra ngoài một cách tự nhiên.
    * **Font chữ:** Sử dụng một font chữ hiện đại, không chân (sans-serif), dễ đọc. Kích thước chữ đủ lớn để đọc mà không cần phóng to quá nhiều.
3.  **Độ Chính xác Văn bản:**
    * **Tuyệt đối không có lỗi chính tả:** Đảm bảo mọi từ, cụm từ, và nhãn trên sơ đồ tư duy phải được viết đúng chính tả Tiếng Anhd 100%.
    * **Ngôn ngữ:** Toàn bộ văn bản trên sơ đồ tư duy phải bằng **Tiếng Anh**.
    * **Tóm tắt Hiệu quả:** Các nhãn và mô tả trên sơ đồ phải ngắn gọn, súc tích nhưng vẫn truyền tải đủ thông tin từ Tài liệu nguồn.

**Đầu ra:** Một hình ảnh sơ đồ tư duy hoàn chỉnh.

Tài liệu nguồn:
{merge}
"""
    # Chỗ này nên parse nguyên tài liệu hay xử lý thế nào ? (xử lý kiểu tóm tắt theo kiểu mong muốn)
    MARK_DOWN_PROMPT = """
Bạn đóng vai trò là một "OCR ENGINE" (Máy xử lý OCR tự động).

NHIỆM VỤ: Chuyển đổi hình ảnh/tài liệu đầu vào thành định dạng Markdown thô (Raw Markdown).

*** QUY TẮC CẤM (STRICT NEGATIVE CONSTRAINTS) - TUÂN THỦ TUYỆT ĐỐI ***
1. KHÔNG được giao tiếp, chào hỏi (ví dụ: "Cảm ơn bạn", "Chào bạn").
2. KHÔNG được giải thích quy trình hay đưa ra đề xuất (ví dụ: "Mình sẽ làm...", "Do tài liệu dài...").
3. KHÔNG được hỏi ý kiến hay xác nhận (ví dụ: "Bạn có đồng ý...", "Xác nhận giúp mình...").
4. KHÔNG chia nhỏ task hay báo cáo tiến độ. Hãy xử lý TOÀN BỘ nội dung được cung cấp trong input ngay lập tức.
5. KHÔNG thêm bất kỳ dòng mở đầu hay kết thúc nào (như "Dưới đây là kết quả...").

Instructions:

1. PHÂN TÍCH VÀ TIỀN XỬ LÝ:
   a. Phân tích kỹ toàn bộ tài liệu gốc.
   b. **Thực hiện bước làm sạch (Cleanup):** Loại bỏ các ký tự điều khiển (control characters) hoặc dấu xuống dòng/khoảng trắng thừa không thuộc về nội dung gốc, nhằm đảm bảo tài liệu đầu vào "sạch" nhất có thể.

2. XÁC ĐỊNH CẤU TRÚC:
   a. Xác định chính xác cấu trúc tài liệu, bao gồm các cấp tiêu đề (header1, header2, header3, ...).
   b. Nhận diện các thành phần phức tạp như danh sách lồng nhau (nested lists), khối mã (code blocks), bảng, và siêu liên kết (hyperlinks).

3. CHUYỂN ĐỔI SANG MARKDOWN:
   Áp dụng quy tắc vàng về tính toàn vẹn dữ liệu:
   - **Giữ nguyên 100% nội dung gốc:** không thêm, không bớt, không tóm tắt, không diễn giải, không sửa lỗi nội dung trong tài liệu.  
   - Giữ nguyên thứ tự trình bày, định dạng và bố cục: **bold**, *italic*, `inline code`, dấu câu, ký tự đặc biệt.  

4. ÁP DỤNG ĐỊNH DẠNG CỤ THỂ:

   a. **Tiêu đề:** Áp dụng Markdown header tương ứng với cấp tiêu đề trong tài liệu gốc (#, ##, ###, ...).  
   b. **Danh sách (Bullet/Numbering):** Giữ nguyên kiểu danh sách. **Đặc biệt, sử dụng thụt lề (indentation) chính xác** cho các danh sách lồng nhau (nested lists) để đảm bảo cấp độ cấu trúc.  
   c. **Bảng:**
      - Nếu bảng đơn giản (cấu trúc hàng/cột tiêu chuẩn) → chuyển sang bảng Markdown.
      - Nếu bảng phức tạp (merged cells, nhiều dòng tiêu đề) → mô tả nội dung bảng một cách chi tiết, không được bỏ sót bất kỳ thông tin quan trọng nào.
   d. **Hình ảnh:** Viết mô tả ngắn gọn nội dung hình ảnh theo dạng: `![mô tả hình ảnh]`.
   e. **Siêu liên kết (Hyperlink):** Chuyển đổi sang cú pháp Markdown chuẩn: `[text hiển thị](URL)`.
   f. **Khối mã lớn (Code Blocks):** Sử dụng **fenced code blocks** (```ngôn ngữ ... ```) và cố gắng xác định ngôn ngữ lập trình nếu có thể để hỗ trợ highlight cú pháp.

5. ĐẦU RA CUỐI CÙNG:
   - Không được tạo thêm bất kỳ nội dung nào ngoài tài liệu gốc.
   - Đảm bảo bản Markdown cuối cùng phản ánh chính xác cấu trúc và nội dung bản gốc.

**HOÀN THÀNH NHIỆM VỤ BẰNG CÁCH CHỈ XUẤT RA ĐÚNG ĐỊNH DẠNG MARKDOWN.**

"""

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

    #     QUESTION_extractor_PROMPT = """
    # xử lý câu hỏi các câu hỏi, loại bỏ trùng lặp, đảm bảo chỉ giữ lại
    # các câu hỏi liên quan, đa dạng và không dư thừa.
    # {good_questions}
    # """

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
**Mục tiêu:** Tổng hợp các bản tóm tắt và ngữ cảnh hỗ trợ thành một bản tóm tắt khoa học, hoàn chỉnh, không sai lệch, được tổ chức theo cấu trúc số thứ tự chuyên nghiệp (1, 2, 3 và 1.1, 1.2, 1.3...).

**Thông tin đầu vào:**
1. Các bản tóm tắt ban đầu từ các phần khác nhau của tài liệu:
{document}
2. Các ngữ cảnh hỗ trợ tương ứng:
{context}

**Yêu cầu đầu ra:**
1. **Tổng hợp thông tin:** Gộp tất cả các bản tóm tắt đã cho thành một bản tóm tắt duy nhất, bao gồm toàn bộ các ý chính.
2. **Kiểm chứng tính chính xác:** Sử dụng các ngữ cảnh hỗ trợ để kiểm tra và đảm bảo bản tóm tắt cuối cùng không chứa bất kỳ sai lệch nào về mặt nội dung.
3. **Nguyên tắc nội dung:**
    * Phần nội dung chính của bản tóm tắt **phải dựa hoàn toàn** trên các bản tóm tắt ban đầu đã cung cấp trong `{document}`.
    * Các ngữ cảnh hỗ trợ trong `{context}` **chỉ được dùng để kiểm chứng/xác nhận** tính chính xác của thông tin.
4. **Cấu trúc số thứ tự khoa học (BẮT BUỘC):** Trình bày bản tóm tắt cuối cùng dưới dạng có cấu trúc rõ ràng, sử dụng **số thứ tự** cho các mục lớn và **số thứ tự thập phân** cho các mục nhỏ.
5. **Ngôn ngữ:** Trong bản tóm tắt, **tuyệt đối không** được nhắc đến các từ mang tính kỹ thuật của quá trình xử lý như: “tài liệu”, “ngữ cảnh”, “bản tóm tắt”, “thông tin đầu vào”, hoặc “nguyên tắc nội dung”.

**Định dạng BẮT BUỘC phải tuân theo:**
1. **Tiêu đề Mục Lớn Thứ Nhất (Ví dụ: Tổng quan và Mục tiêu)**
    1.1. Chi tiết nhỏ thứ nhất (Ví dụ: Vấn đề được giải quyết).
    1.2. Chi tiết nhỏ thứ hai (Ví dụ: Đóng góp chính).
        * Chi tiết phụ cấp 3 (sử dụng dấu gạch đầu dòng nếu cần phân tích sâu hơn 1.2.x).
2. **Tiêu đề Mục Lớn Thứ Hai (Ví dụ: Kiến trúc Mô hình Đề xuất)**
    2.1. Thành phần A: [Mô tả ngắn gọn].
    2.2. Thành phần B: [Mô tả ngắn gọn].
3. **Tiêu đề Mục Lớn Thứ Ba (Ví dụ: Kết quả và Đánh giá)**
    3.  1. Hiệu suất chính: [Giá trị/thông số].
    3.2. So sánh với phương pháp hiện tại (SOTA).

**Bắt đầu tạo bản tóm tắt khoa học, có cấu trúc số thứ tự.**
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
Bạn là chuyên gia trả lời câu hỏi dựa trên tài liệu được cung cấp.

### CÂU HỎI:
{question}
### Khi câu hỏi người dùng yêu cầu chỗ đó, vùng này,đoạn này thì nó nằm ở đây, là đoạn văn người dùng đã chọn :
{selected_text}

### CÁC BƯỚC THỰC HIỆN :

-Phân tích kỹ câu hỏi và đoặn văn người dùng đã chọn để xác định câu hỏi của người dùng

**Nếu câu hỏi LIÊN QUAN đến tài liệu nguồn hoặc yêu cầu giải thích một vùng/đoạn trong tài liệu**
- Giải thích rõ ràng, đầy đủ, có logic
- Trích dẫn hoặc diễn giải chính xác từ tài liệu
- Chỉ sử dụng thông tin có trong tài liệu, không thêm kiến thức bên ngoài

**Nếu câu hỏi KHÔNG LIÊN QUAN hoặc nằm ngoài phạm vi tài liệu:**
- Từ chối trả lời một cách lịch sự
- Giải thích ngắn gọn lý do (tài liệu không đề cập đến nội dung này)
- Gợi ý người dùng đặt câu hỏi phù hợp hơn với nội dung tài liệu

**Ví dụ từ chối:**
"Xin lỗi, câu hỏi này nằm ngoài phạm vi tài liệu được cung cấp. Tài liệu hiện tại tập trung vào [chủ đề X]. Bạn có thể đặt câu hỏi liên quan đến nội dung này để tôi hỗ trợ tốt hơn."

### NGUYÊN TẮC BẮT BUỘC:
- KHÔNG suy đoán hoặc bịa thông tin
- KHÔNG sử dụng kiến thức ngoài tài liệu nguồn
- KHÔNG trả lời các câu hỏi về chủ đề không được đề cập trong tài liệu

### TÀI LIỆU NGUỒN:
{documents}
"""
    QUESTIONS_GEN_PROMPT = """
Bạn là chuyên gia tạo câu hỏi trắc nghiệm cho môn lập trình hướng đối tượng bằng Java.
Hãy tạo câu hỏi trắc nghiệm đòi hỏi hiểu sâu, tư duy phản biện, và phân tích chi tiết dựa vào tài liệu nguồn bên dưới.
Các câu hỏi không chỉ ghi nhớ thông tin đơn thuần, mà còn hướng đến các mức tư duy cao hơn như phân tích, tổng hợp, và đánh giá.

CÁC BƯỚC THỰC HIỆN:
1. Xác định các khái niệm hoặc thuật ngữ quan trọng trong tài liệu và hiểu rõ định nghĩa hoặc vai trò của chúng.
2. Xác định mối quan hệ giữa các khái niệm (so sánh, đối lập, liên kết, phụ thuộc) trong tài liệu nguồn.
3. Xác định các ví dụ hoặc ứng dụng được nhắc đến, đặc biệt là các ví dụ code.
4. Mỗi câu hỏi phải tập trung vào MỘT khái niệm duy nhất trong tài liệu nguồn bên dưới.
5. Tạo 4 lựa chọn (options) trong đó phải có ít nhất 2 lựa chọn nhiễu (distractors) hợp lý, liên quan đến chủ đề để gây khó khăn cho người học.
6. Viết lời giải thích (explanation) chi tiết cho đáp án đúng.

YÊU CẦU SỐ LƯỢNG CÂU HỎI & MỨC ĐỘ KHÓ (difficulty): 
- 4 câu easy
- 3 câu medium
- 3 câu hard
(Tổng cộng 10 câu hỏi)

YÊU CẦU ĐẦU RA:
- Trả về **danh sách JSON** duy nhất theo đúng cấu trúc bên dưới.
- **Không giải thích gì thêm ngoài JSON.**
- Mỗi câu hỏi phải độc lập, không trùng ý, không lặp ý.

CẤU TRÚC JSON (BẮT BUỘC):
[
  {{"id":"q1",
    "type":"multiple_choice",
    "difficulty":"easy", 
    "question":"Câu hỏi được tạo ra từ tài liệu nguồn, phải ngắn gọn và rõ ràng.",
    "options":["A. Lựa chọn đúng","B. Lựa chọn nhiễu 1 (phải hợp lý)","C. Lựa chọn nhiễu 2 (phải hợp lý)","D. Lựa chọn nhiễu 3 (phải hợp lý)"],
    "correct_answer":0, 
    "explanation":"Giải thích chi tiết tại sao đáp án này là đúng và giải thích ngắn gọn tại sao các nhiễu là sai."
  }},
  // Thêm các câu hỏi khác ở các mức độ medium và hard tương ứng
]

LƯU Ý QUAN TRỌNG:
- Trường "id" phải là duy nhất (ví dụ: q1, q2, q3...).
- Trường "type" luôn là "multiple_choice".
- Trường "difficulty" phải là "easy", "medium" hoặc "hard" theo đúng yêu cầu số lượng.
- Trường "correct_answer" phải là chỉ số số nguyên từ 0 đến 3 (tương ứng với A, B, C, D).
- Có 1–2 câu hỏi nên yêu cầu đọc hiểu hoặc phân tích code.
- Tất cả câu hỏi phải khác nhau và không bị trùng ý.

TÀI LIỆU NGUỒN:
{document}
"""
