from langchain.tools import tool


@tool("developer")
def developer_tool(expression: str) -> float:
    """Công cụ để  sinh ra bài tập, xử lý, review code"""
