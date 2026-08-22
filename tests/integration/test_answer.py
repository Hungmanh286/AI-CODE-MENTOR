import asyncio

import structlog
from langchain_core.messages import HumanMessage

from app.agents.feedback_answer import feedbacks_answer

logger = structlog.get_logger(__name__)

arr = [
    "Vai trò của mạng ARPANET trong sự phát triển của Internet là gì?",
    "Tại sao cấu trúc cơ bản của Internet lại dựa trên mạng TCP/IP?",
    "Vai trò của các tổ chức như IETF và IAB trong quản lý mạng Internet là gì?",
    "Tại sao World Wide Web được xem là một nền tảng quan trọng cho các trình duyệt và ứng dụng web hiện nay?",
    "Phân tích cách thức trình duyệt Web xử lý và hiển thị nội dung từ các trang web dựa trên các công nghệ nào?",
    "Phân tích mối quan hệ giữa các thành phần trong mô hình hệ thống Web nói chung và vai trò của từng thành phần.",
    "Đánh giá tầm quan trọng của việc chuẩn hóa giao thức và bảo mật trong quản lý Internet khi số lượng thiết bị kết nối tăng nhanh.",
    "Phân tích sự khác biệt về chức năng giữa các trình duyệt Web đầu tiên như Mosaic và các trình duyệt hiện đại như Chrome hay Firefox.",
    "Phân tích cách thức các chuẩn HTML, HTTP và URL do Tim Berners-Lee phát triển đã tạo điều kiện cho sự phát triển của World Wide Web như thế nào?",
    "Frontpage 2002 quản lý các file hệ thống nào khi tạo một website từ thư mục trên máy tính?",
    "Trong HTML, thẻ nào được dùng để định nghĩa một đoạn văn bản và có thể chứa các thẻ con như <b>, <i>, <u> để định dạng chữ?",
    "Phân tích vai trò và cách sử dụng thẻ <A> trong HTML để tạo hyperlink và đặt tên đối tượng.",
    "Cách thức tạo một form trong HTML và các thành phần cơ bản thường được sử dụng trong form là gì?",
    "So sánh sự khác biệt về vai trò và cú pháp giữa thẻ <BR> và thẻ <HR> trong HTML.",
    "Phân tích cách Frontpage 2002 cho phép người dùng hiển thị hoặc ẩn các công cụ trên thanh công cụ như thế nào.",
    "Dựa vào ví dụ HTML cơ bản, hãy phân tích cấu trúc và vai trò của các thẻ <HTML>, <HEAD>, <TITLE>, và <BODY> trong một trang web.",
    "Phân tích cách sử dụng các thuộc tính như width, border, cell padding, cell spacing trong thẻ <TABLE> để điều chỉnh bố cục bảng trong HTML.",
    'Đánh giá tầm quan trọng của việc xóa các thư mục hệ thống như "_private", "_vti_cnf", "_vti_pvt" khi đưa website lên mạng trong Frontpage 2002.',
    "Màu sắc đóng vai trò như thế nào trong thiết kế đồ họa trên Web so với thiết kế truyền thống?",
    "Điểm khác biệt chính giữa đồ họa trên Web và đồ họa in ấn là gì?",
    "Tại sao việc tối ưu kích thước tập tin và chất lượng hình ảnh lại quan trọng trong xử lý đồ họa cho Web?",
    "Phần mềm nào được đề cập là phổ biến nhất cho việc xử lý đồ họa trên Web và trong những ngữ cảnh nào chúng được sử dụng?",
    "Phân tích sự khác biệt trong cách thiết lập lề bên trái và lề bên phải của đoạn văn bản trong HTML và CSS dựa trên ví dụ đã cho.",
    "Trong ví dụ về danh sách không đánh số thứ tự, các kiểu danh sách disc, circle, square, và none khác nhau như thế nào về mặt hiển thị?",
    "Phân tích tác động của việc sử dụng thuộc tính 'display: none' trong CSS đối với khả năng truy cập và SEO của trang web.",
    "Phân tích cách sử dụng hình ảnh làm đơn vị đánh dấu trong danh sách và ảnh hưởng của thuộc tính 'list-style-position' đến vị trí của dấu đầu dòng.",
    "Đánh giá ưu và nhược điểm của việc sử dụng phần mềm Photoshop và CorelDRAW trong quy trình xử lý đồ họa cho Web dựa trên tài liệu.",
    "Trong CSS, thuộc tính 'list-style-type' có vai trò gì khi áp dụng cho các thẻ danh sách?",
    "So sánh sự khác biệt giữa các kiểu danh sách được thiết lập bằng 'list-style-type' trong thẻ <ol> như 'decimal', 'lower-roman', và 'upper-roman'.",
    "Phân tích cách sử dụng thuộc tính 'list-style-image' trong CSS và ảnh hưởng của nó đến hiển thị danh sách.",
    "Thuộc tính CSS nào được sử dụng để điều chỉnh chiều cao dòng trong đoạn văn và tác dụng của nó là gì?",
    "Phân tích sự khác biệt về vị trí của đoạn văn bản khi sử dụng 'position: relative' với các giá trị 'left: 20px' và 'left: -20px'.",
    "Trong đoạn mã CSS, khi nào nên sử dụng 'position: absolute' thay vì 'position: relative' để định vị một phần tử, và ảnh hưởng của nó đến bố cục trang là gì?",
    "Phân tích tác động của thuộc tính 'visibility: hidden' so với 'display: none' trong việc ẩn một phần tử HTML.",
    "Dựa vào ví dụ về các chế độ màu RGB và CMYK, hãy đánh giá ưu nhược điểm của từng chế độ trong việc sử dụng cho màn hình và in ấn.",
    "Phân tích cách hoạt động của chế độ màu Index và ảnh hưởng của nó đến chất lượng hình ảnh và kích thước tệp tin.",
    "Lệnh nào trong CorelDraw được sử dụng để tạo một file tài liệu mới và khác biệt như thế nào so với lệnh 'New from Template'?",
    "Trong CorelDraw, chức năng của lệnh 'Revert' là gì và điều kiện để lệnh này có thể thực hiện được?",
    "Khi sử dụng lệnh Open trong CorelDraw, làm thế nào để mở nhiều file cùng lúc và những hạn chế nào có thể gặp phải khi mở file từ các ứng dụng khác?",
    "Mục đích và cách sử dụng lệnh 'Publish to PDF' trong CorelDraw là gì?",
    "Phân tích cách điều chỉnh sắc độ màu trong CorelDraw qua các bước và các thành phần điều khiển chính trong hộp thoại Hue and Saturation.",
    "So sánh vai trò của các trục Hue, Saturation và Lightness trong việc điều chỉnh màu sắc ảnh trong CorelDraw.",
    "Phân tích quy trình xuất ảnh cho web trong CorelDraw và các tham số quan trọng cần thiết để tối ưu dung lượng ảnh.",
    "Trong CorelDraw, khi tạo một lớp mới và vùng chọn hình chữ nhật, lệnh nào được sử dụng để chỉnh độ rộng và màu sắc đường bao, và tại sao thao tác này quan trọng trong thiết kế?",
    "Đọc và phân tích đoạn mã giả sau: Nếu bạn muốn mở nhiều file tài liệu trong CorelDraw, bạn sẽ làm thế nào? Giải thích cơ chế hoạt động của lệnh Open trong trường hợp này dựa trên tài liệu.",
    "Trong Java, khái niệm 'đóng gói' (encapsulation) giúp ích gì trong việc bảo vệ dữ liệu của một đối tượng?",
    "Phân tích sự khác biệt giữa phương thức 'Group' và 'Ungroup' trong quản lý đối tượng trong Java.",
    "Tại sao việc giữ nguyên vị trí tương đối giữa các đối tượng trong một nhóm lại quan trọng trong thiết kế phần mềm hướng đối tượng?",
    "Trong Java, khi nào nên sử dụng phương thức 'Group' để quản lý các đối tượng thay vì xử lý từng đối tượng riêng lẻ?",
    "Phân tích cách thức hoạt động của lệnh 'Group' dựa trên đoạn mô tả và giải thích tác động của nó đến trạng thái các đối tượng được nhóm.",
    "Đọc đoạn mô tả về lệnh Group và Ungroup, hãy phân tích ưu và nhược điểm của việc sử dụng nhóm đối tượng trong thiết kế giao diện người dùng.",
    "Giả sử bạn có một nhóm các đối tượng đã được Group, nếu bạn muốn thay đổi vị trí một đối tượng con trong nhóm mà không ảnh hưởng đến các đối tượng khác, bạn sẽ xử lý như thế nào? Phân tích dựa trên đặc điểm của Group.",
    "So sánh và đánh giá tác động của việc sử dụng Group trong quản lý đối tượng so với việc quản lý từng đối tượng riêng biệt trong một ứng dụng Java phức tạp.",
    "Phân tích đoạn code giả định sau: nếu một nhóm đối tượng được Group, và sau đó một đối tượng con bị xóa, ảnh hưởng như thế nào đến nhóm và các đối tượng còn lại?",
    "Quá trình tạo Site profile trong WS_FTP Pro bao gồm những bước chính nào để thiết lập kết nối FTP?",
    "Tại sao WS_FTP Pro cung cấp hai giao diện Classic và Explorer, và sự khác biệt chính giữa chúng là gì?",
    "Chức năng của menu Sites trong WS_FTP Pro là gì và nó hỗ trợ người dùng như thế nào trong việc quản lý các site profile?",
    "Lệnh get và put trong FTP có vai trò gì trong việc truyền nhận file giữa máy cục bộ và máy ở xa?",
    "Phân tích quy trình kết nối tới một site đã tạo trong WS_FTP Pro sau khi hoàn thành Site profile.",
    "Tại sao người dùng mới nên bắt đầu với giao diện Classic của WS_FTP Pro thay vì giao diện Explorer?",
    "Phân tích các quyền hạn có thể ảnh hưởng đến việc thực hiện các thao tác trên Remote System trong WS_FTP Pro và tác động của chúng đến người dùng.",
    "Đánh giá vai trò của hộp thoại Site Options trong việc quản lý kết nối FTP và các thông số có thể thay đổi trong đó.",
    "Phân tích sự khác biệt về chức năng và giao diện giữa các menu File, Edit, View, Sites, Options, Tools, Help trong WS_FTP Pro và vai trò của chúng trong quản lý FTP site.",
    "CGI hoạt động như thế nào khi một người dùng truy cập một trang web viết bằng CGI?",
    "Điểm khác biệt cơ bản giữa Javascript và các ngôn ngữ lập trình web phía server như PHP hay JSP là gì?",
    "Tại sao Perl được chọn làm ngôn ngữ lập trình web động trong nhiều trường hợp?",
    "PHP có ưu điểm gì khi nhúng mã vào trong HTML so với các ngôn ngữ khác?",
    "Phân tích đoạn mã CGI viết bằng Perl dưới đây và cho biết chức năng chính của nó:\n#!/usr/local/bin/perl  \nprint “content-type:text/html\\n\\n”;  \nprint “Hello, World!\\n”;",
    "So sánh vai trò của JSP và PHP trong việc xử lý dữ liệu phía server trên các trang web động.",
    "Đánh giá ưu và nhược điểm của việc sử dụng CGI so với các ngôn ngữ lập trình web động hiện đại như PHP hay JSP.",
    "Phân tích mối quan hệ giữa VBScript và ASP trong việc phát triển ứng dụng web.",
    "Trong VBScript, tại sao việc hiểu rõ phạm vi biến và kiểu dữ liệu lại quan trọng khi viết các script cho ASP?",
    "Web Server hoạt động dựa trên mô hình nào và sử dụng giao thức gì để truyền dữ liệu?",
    "Tiêu chí nào quan trọng khi lựa chọn một Web Server phù hợp cho môi trường triển khai?",
    "Điểm khác biệt chính giữa Apache Web Server và IIS Web Server là gì?",
    "Quá trình tạo một Web Site mới trong IIS bắt đầu bằng thao tác nào và cần cung cấp những thông tin gì?",
    "Phân tích vai trò của các đối tượng Drive, Folder và File trong cấu trúc quản lý nội dung của IIS.",
    "Tại sao việc thiết lập các tham số bảo mật như xác thực người dùng và quyền đọc/ghi lại quan trọng trong cấu hình Web Site trên IIS?",
    "So sánh ưu điểm của SunOne Web Server với Apache Web Server dựa trên mô tả về tính năng và nền tảng phát triển.",
    "Phân tích các bước cần thiết để cài đặt và cấu hình IIS nhằm phục vụ các trang web và ứng dụng trên máy chủ Windows.",
    "Đọc đoạn mã hoặc mô tả quy trình tạo Web Site mới trong IIS và xác định các bước cần thiết để đảm bảo quyền truy cập an toàn cho người dùng.",
    "Webportal là gì và vai trò của nó trong việc liên kết thông tin từ nhiều website khác nhau?",
    "Tại sao việc xác định mục đích, yêu cầu và đối tượng sử dụng lại quan trọng trong thiết kế Webportal?",
    "Phương pháp Pareto (luật 80-20) được áp dụng như thế nào trong việc xác định vấn đề mấu chốt khi thiết kế website?",
    "Các bước chính trong kỹ thuật khảo sát và thu thập thông tin để xây dựng Webportal là gì?",
    "Phân tích vai trò của việc hỏi “tại sao?” trong quá trình phân tích yêu cầu thiết kế website.",
    "Phân biệt giữa Webportal và các website thông thường dựa trên cách thức quản lý và liên kết thông tin.",
    "Đánh giá tầm quan trọng của việc lựa chọn các mức bảo mật phù hợp trong quá trình xây dựng Webportal.",
    "Phân tích mối quan hệ giữa việc xác định mục đích thiết kế và việc lựa chọn các thành phần chính của website.",
    "Phân tích đoạn code hoặc mô hình logic web (Hình 10.9) để nhận diện các thành phần cơ sở dữ liệu quan trọng trong Webportal.",
]


async def test_feedbacks_answer():
    """Test feedbacks_answer agent with 100 questions"""

    logger.info(f"Starting test with {len(arr)} questions...")
    logger.info("=" * 80)

    results = []

    for idx, question in enumerate(arr):
        logger.info(f"\n[{idx + 1}/{len(arr)}] Processing question: {question[:80]}...")

        try:
            # Tạo input cho agent
            inputs = {"messages": [HumanMessage(content=question)]}

            # Tạo config
            config = {"configurable": {"thread_id": "test_session_feedbacks"}}

            # Gọi agent
            result = await feedbacks_answer.ainvoke(inputs, config=config)

            # Lấy answer từ result
            answer = (
                result["messages"][-1].content
                if result.get("messages")
                else "No answer"
            )

            results.append(
                {
                    "question_index": idx + 1,
                    "question": question,
                    "answer": answer,
                    "status": "success",
                }
            )

            logger.info(f"✓ Completed: {answer[:100]}...")

        except Exception as e:
            logger.info(f"✗ Error: {str(e)}")
            results.append(
                {
                    "question_index": idx + 1,
                    "question": question,
                    "answer": None,
                    "status": "error",
                    "error": str(e),
                }
            )

    # Tổng kết
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)
    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = sum(1 for r in results if r["status"] == "error")

    logger.info(f"Total questions: {len(arr)}")
    logger.info(f"Successful: {success_count}")
    logger.info(f"Failed: {error_count}")
    logger.info(f"Success rate: {success_count / len(arr) * 100:.2f}%")

    return results


if __name__ == "__main__":
    asyncio.run(test_feedbacks_answer())
