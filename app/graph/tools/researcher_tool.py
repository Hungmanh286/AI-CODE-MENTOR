from langchain.tools import tool


@tool("researcher")
def researcher_tool(expression: str) -> float:
    """Công cụ để tạo tài liệu cá nhân hóa"""
