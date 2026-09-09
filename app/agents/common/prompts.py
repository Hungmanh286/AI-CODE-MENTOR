"""Prompts shared by more than one agent (summarising, citation, mind-map)."""


class Prompts:
    # Modules for question answer generation
    SUMMARIZE_CHUNK_SUMMARY_PROMPT = """
Bạn là trợ lý AI chuyên tóm tắt tài liệu học tập và kỹ thuật.
Nhiệm vụ của bạn là đọc nội dung đoạn trích dưới đây và viết một bản tóm tắt súc tích, bao quát toàn bộ các luận điểm và khái niệm chính.

YÊU CẦU:
1. Giữ lại đầy đủ các thông tin cốt lõi, thuật ngữ kỹ thuật và định nghĩa quan trọng.
2. Trình bày mạch lạc, logic, văn phong khách quan và chính xác.
3. Tuyệt đối không sử dụng các từ ngữ siêu hình hay tự quy chiếu như "tài liệu này", "bản tóm tắt", "đoạn trích trên".
4. Không thêm các suy đoán hoặc kiến thức nằm ngoài nội dung được cung cấp.

NỘI DUNG:
{document}
"""

    MIND_MAP_PROMPT = """
Bạn là chuyên gia thiết kế sơ đồ tư duy (mind map) giáo dục và kỹ thuật.
Mục tiêu: Tạo một sơ đồ tư duy trực quan, cô đọng, có cấu trúc phân cấp rõ ràng và độ chính xác cao dựa trên nội dung nguồn.

YÊU CẦU HÌNH ẢNH VÀ NỘI DUNG:
1. Chủ đề trung tâm: Đặt chủ đề chính ở vị trí trung tâm, các nhánh cấp 1 và cấp 2 phát triển ra xung quanh có tính hệ thống.
2. Phong cách thiết kế:
   - Hiện đại, tối giản (flat design), đường nét mạch lạc, bố cục cân đối và dễ đọc.
   - Tông màu sáng, chuyên nghiệp (như pastel hoặc màu có độ tương phản cao trên nền trắng/sáng).
   - Font chữ không chân (sans-serif), kích thước phân cấp rõ rệt theo từng cấp độ thông tin.
3. Độ chính xác nội dung:
   - Ngôn ngữ: Sử dụng ngôn ngữ chính của tài liệu nguồn (ưu tiên Tiếng Việt nếu tài liệu tiếng Việt, Tiếng Anh nếu tài liệu tiếng Anh).
   - Tuyệt đối đúng chính tả 100%, thuật ngữ kỹ thuật giữ nguyên dạng chuẩn.
   - Nhãn (labels) trên từng nhánh phải ngắn gọn, súc tích (dạng từ khóa hoặc cụm từ ngắn gọn) nhưng thể hiện trọn vẹn thông tin.

ĐẦU RA: Hình ảnh sơ đồ tư duy hoàn chỉnh, bao quát toàn bộ nội dung tài liệu.

TÀI LIỆU NGUỒN:
{merge}
"""

    EXTRACTIVE_SUMMARIZE_PROMPT = """
Bạn là chuyên gia trích xuất câu then chốt (extractive summarization).

Nhiệm vụ: Trích xuất các câu quan trọng nhất thể hiện luận điểm chính từ đoạn trích dưới đây.

NGUYÊN TẮC BẮT BUỘC:
1. Chỉ chọn các câu xuất hiện NGUYÊN VĂN trong văn bản gốc.
2. TUYỆT ĐỐI KHÔNG viết lại, không diễn giải (paraphrase), không gộp câu hoặc sửa từ ngữ.
3. Chọn lọc các câu chứa thông tin định nghĩa, nguyên lý hoặc kết quả cốt lõi; loại bỏ trùng lặp.
4. Giữ nguyên thứ tự xuất hiện của các câu theo đúng tiến trình văn bản.

ĐỊNH DẠNG ĐẦU RA:
- Trả về danh sách các câu đã trích xuất, mỗi câu trên một dòng riêng biệt.
- Không thêm bất kỳ lời dẫn, số thứ tự hay giải thích nào khác.

ĐOẠN TRÍCH:
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
Bên dưới là một tài liệu:
{document}

Hãy trích xuất các ý chính quan trọng nhất của tài liệu.
"""

    # Merge normal phân cấp
    HMerge_SUMMARY_PROMPT = """
Bên dưới là các bản tóm tắt từng phần của một tài liệu:
{very_document}

Hãy tổng hợp các phần tóm tắt trên thành một văn bản tóm tắt tổng thể hoàn chỉnh, mạch lạc và bao quát toàn bộ nội dung cốt lõi.
Yêu cầu: Không dùng các từ tự quy chiếu như "tài liệu", "các bản tóm tắt trên", "phần này".
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
Mục tiêu: Tổng hợp các bản tóm tắt và ngữ cảnh hỗ trợ thành một bản tóm tắt khoa học, hoàn chỉnh, không sai lệch, được tổ chức theo cấu trúc phân cấp chuyên nghiệp (1, 2, 3 và 1.1, 1.2, 1.3...).

THÔNG TIN ĐẦU VÀO:
1. Các bản tóm tắt ban đầu từ các phần khác nhau của tài liệu:
{document}
2. Các ngữ cảnh hỗ trợ tương ứng:
{context}

YÊU CẦU ĐẦU RA:
1. Tổng hợp thông tin: Hợp nhất các bản tóm tắt thành một bài tổng thuật duy nhất, không bỏ sót luận điểm quan trọng.
2. Kiểm chứng tính xác thực: Dùng các ngữ cảnh hỗ trợ để đối chiếu, loại bỏ triệt để sai lệch nội dung.
3. Nguyên tắc nội dung:
   - Nội dung chính bám sát thông tin trong {document}.
   - Ngữ cảnh hỗ trợ trong {context} dùng để kiểm chứng và làm rõ tính chính xác.
4. Cấu trúc số phân cấp chuẩn mực: Sử dụng số thứ tự cho đề mục lớn và số thập phân cho đề mục con (1.1, 1.2, 1.3...).
5. Ngôn ngữ: Tuyệt đối không dùng các từ kỹ thuật siêu dữ liệu như "tài liệu", "ngữ cảnh hỗ trợ", "bản tóm tắt", "thông tin đầu vào".

ĐỊNH DẠNG MẪU BẮT BUỘC:
1. Tiêu đề Mục Lớn Thứ Nhất (Ví dụ: Tổng quan và Mục tiêu)
   1.1. Chi tiết phân tích thứ nhất
   1.2. Chi tiết phân tích thứ hai
2. Tiêu đề Mục Lớn Thứ Hai (Ví dụ: Kiến trúc và Phương pháp)
   2.1. Thành phần A: Mô tả chi tiết
   2.2. Thành phần B: Mô tả chi tiết
3. Tiêu đề Mục Lớn Thứ Ba (Ví dụ: Kết quả và Ứng dụng)
   3.1. Hiệu năng và đánh giá
   3.2. Đánh giá và so sánh thực nghiệm
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

    SUMMARIZE_PROMPT = """
Bạn là trợ lý AI tóm tắt tài liệu học tập.
Hãy tóm tắt đoạn văn sau một cách ngắn gọn, súc tích bằng tiếng Việt và giữ lại các ý chính quan trọng:

---
{text}
---
Tóm tắt:
"""

    MIND_MAP_COMPLETION_PROMPT = """
Bạn hãy thông báo cho người dùng một cách ngắn gọn, lịch sự rằng sơ đồ tư duy (mind map) đã được khởi tạo thành công và sẵn sàng để xem.
"""
