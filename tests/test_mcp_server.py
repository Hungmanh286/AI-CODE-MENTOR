import numexpr as ne
from fastmcp import FastMCP

mcp = FastMCP("PDFExtractor")


latest_uploaded_file: str | None = None


@mcp.tool()
def calculator_tool(expression: str) -> float:
    """Công cụ thực hiện tính toán và trả về giá trị cho các biểu thức, phép toán đầu vào.

    Args:
        expression (str): expression to evaluate

    Returns:
        float: result of the expression
    """
    try:
        result = ne.evaluate(expression).item()
        return f"{expression} = {result}"
    except Exception:
        return expression


@mcp.tool()
def echo_tool(message: str) -> str:
    """Công cụ trả về chính xác tin nhắn người dùng đã nhập vào.

    Args:
        message (str): message to echo

    Returns:
        str: echoed message
    """
    return message


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
