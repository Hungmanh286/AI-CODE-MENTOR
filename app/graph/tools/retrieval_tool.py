from sqlmodel import select, Session
from langchain.tools import tool
from app.schema.lesson import Lesson
from app.config import settings


def get_lesson_by_query(query: str) -> Lesson | None:
    with Session(settings._app_db_engine) as session:
        statement = select(Lesson).where(Lesson.lesson_name.ilike(f"%{query}%"))
        result = session.exec(statement).first()
        return result


@tool("retriever")
def retriever_tool(query: str) -> str:
    """A tool to retrieve lesson content based on a query.
    Args:
        query (str): get the exact content of the question
    Returns:
        str: The full content of the lesson if found.
            If no matching lesson is found, returns the string
            "No relevant".
    """

    result = get_lesson_by_query(query)
    if result:
        return result.content
    return "No relevant"
