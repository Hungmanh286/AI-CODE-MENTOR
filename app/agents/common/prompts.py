"""Prompts shared by more than one agent (summarising, citation, mind-map)."""


class Prompts:
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
