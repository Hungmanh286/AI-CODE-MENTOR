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
Bạn là chuyên gia thiết kế sơ đồ tư duy (mind map) từ tài liệu được cung cấp.
Yêu cầu: trình bày theo phong cách hiện đại, tối giản, sử dụng tông màu sáng, nền trắng, bố cục rõ ràng, dễ đọc và trực quan.

Tài liệu nguồn:
{merge}
"""
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
Bạn là chuyên gia tạo các lựa chọn trắc nghiệm cho môn lập trình dựa vào danh sách các câu hỏi và đoạn văn liên quan đến câu hỏi tương ứng bên dưới
Hãy sinh ra các lựa chọn trắc nghiệm dạng có 4 lựa chọn lựa chọn dựa vào danh sách câu hỏi và tài liệu bên dưới.

Yêu cầu:
- Mỗi câu hỏi có 4 lựa chọn lựa chọn, bắt đầu bằng: A., B., C., D.
- Chỉ một lựa chọn đúng.
- Ba lựa chọn nhiễu (distractors) phải:
  • Phù hợp với ngữ cảnh.
  • Liên quan trực tiếp đến nội dung.
  • Phản ánh những hiểu lầm hoặc lỗi tư duy thường gặp, nhưng không được mâu thuẫn hoặc sai lệch hoàn toàn với nội dung.

Lưu ý:
related_passage phải giữ đúng nguyên văn đoạn văn liên quan đến câu hỏi.
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
    "related_passage": "<đoạn văn liên quan>",
}},
  ...
]
Giải thích từ khóa về danh sách câu hỏi : 
question : là nội dung câu hỏi
related_passage : là đoạn văn liên quan đến câu hỏi đó 

Danh sách câu hỏi:\n
{questions}
"""

    EVALUATE_QA_PROMPT = """
Bạn là một chuyên gia đánh giá chất lượng câu hỏi trắc nghiệm cho môn lập trình dựa vào danh sách câu hỏi và đoạn văn liên quan đến câu hỏi đó ở bên dưới

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
chunk_index là chỉ số của chunk trong tài liBạn là chuyên gia OCR có nhiệm vụ chuyển đổi tài liệu sang Markdown.

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

**HOÀN THÀNH NHIỆM VỤ BẰNG CÁCH CHỈ XUẤT RA ĐÚNG ĐỊNH DẠNG MARKDOWN.**ệu gốc (có trong dòng đầu trong mỗi danh sách câu hỏi từ dữ liệu đầu vào)
YÊU CẦU BẮT BUỘC:
1. CHỈ TRẢ VỀ MỘT JSON HỢP LỆ TRÊN MỘT DÒNG DUY NHẤT. Không có văn bản, giải thích, hay markdown khác.
2. JSON phải tuân thủ cấu trúc trên với 3 key: bad_questions, good_questions, good_question_answer.
3. Mỗi key phải chứa dict với chunk_index là string (ví dụ: "0", "1", "2").
4. Nếu một chunk không có câu hỏi tốt hoặc xấu, trả về danh sách rỗng [] cho chunk đó.
5. Tất cả chunk_index từ đầu vào phải xuất hiện trong cả 3 key của JSON đầu ra.

DỮ LIỆU ĐẦU VÀO:
{question_answers}

"""
    # Lưu ý :
    EVALUATE_AND_SELECT_PROMPT = """
Bạn là một giảng viên chuyên môn về lập trình.

NHIỆM VỤ:
- Chuẩn hoá danh sách câu hỏi trong DỮ LIỆU ĐẦU VÀO.
- Phân tích {query} và {num_chunks} để xác định số lượng câu hỏi bằng kết quả số lượng trong {query} chia cho {num_chunks} (Đây là dấu chia ví dụ 10:5=2)
    • Nếu đề cập rõ số lượng thì sử dụng đúng số đó:
        - nếu trong danh sách câu hỏi đầu vào ko đủ thì phải bổ sung thêm cho đủ
        - nếu trong danh sách đầu vào mà thừa thì phải lọc cho đủ
    • Nếu không đề cập thì mặc định 10 câu hỏi.
LƯU Ý : Nếu có nhiều chunk thì phải có ít nhất 3 câu hỏi từ mỗi chunk.

YÊU CẦU BẮT BUỘC:
- TRẢ VỀ DUY NHẤT MỘT MẢNG JSON HỢP LỆ (bắt đầu bằng [ và kết thúc bằng ])
- KHÔNG THÊM markdown, backticks, giải thích hay text nào khác
- Mỗi câu hỏi phải có đầy đủ 7 trường: id, type, difficulty, question, options, correct_answer, explanation

CẤU TRÚC JSON (VÍ DỤ):
[{{"id":"q1","type":"multiple_choice","difficulty":"medium","question":"Câu hỏi?","options":["A","B","C","D"],"correct_answer":0,"explanation":"Giải thích"}}]

Danh sách câu hỏi đầu vào:
{questions}

CHỈ TRẢ VỀ JSON, KHÔNG CÓ TEXT KHÁC:
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
    # phải lấy được context của ảnh để trả lời câu hỏi
    FEEDBACK_QUESTIONS_PROMPT = """
Bạn là chuyên gia trả lời câu hỏi dựa trên tài liệu được cung cấp.

### CÂU HỎI:
{question}
### VÙNG/ĐOẠN TRONG TÀI LIỆU ĐƯỢC CHỌN(nếu có):
{selected_text}

### CÁC BƯỚC THỰC HIỆN :

-Phân tích kỹ câu hỏi để xác định câu hỏi của người dùng

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
