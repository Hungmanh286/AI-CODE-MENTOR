import os
from mcp.server.fastmcp import FastMCP
from typing import Annotated
from docling.document_converter import DocumentConverter


mcp = FastMCP("PDFExtractor")
converter = DocumentConverter()


UPLOAD_DIR = "/tmp/uploads"
# Biến lưu file upload gần nhất

latest_uploaded_file: str | None = None


@mcp.tool()
async def extract_pdf_text(
    file_path: Annotated[str, "Path to the uploaded PDF file"],
) -> str:
    """

    trích xuất nội dung từ file pdf
    Input:
        file_path (str): Path to PDF file saved on server
    Output:
        Extracted Markdown text
    """
    file_path = "/tmp/uploads/Đề thi Lập trình hướng đối tượng đề số 2 kỳ 2 năm học 2022-2023 – UET.pdf"
    try:
        if not os.path.exists(file_path):
            return f"File not found: {file_path}"

        doc = converter.convert(file_path).document
        text = doc.export_to_markdown()
        return text or "Không trích xuất được nội dung từ PDF."
    except Exception as e:
        return f"Lỗi khi đọc PDF: {e}"


# @mcp.tool()
# async def get_latest_pdf_path() -> str:
#     """
#     Trả về đường dẫn file PDF gần nhất người dùng upload.
#     """
#     global latest_uploaded_file
#     if latest_uploaded_file:
#         return latest_uploaded_file
#     return "Chưa có file nào được upload."


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
