import numexpr as ne
from langchain.tools import tool


@tool("calculator")
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
