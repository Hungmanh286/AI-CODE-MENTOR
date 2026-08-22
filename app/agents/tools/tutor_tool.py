from langchain.tools import tool


@tool("tutor_tool")
def tutor_tool(expression: str) -> float:
    """Công cụ để giải đáp các thắc mắc về tài liệu cá nhân hóa"""
