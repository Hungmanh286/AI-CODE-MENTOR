"""Graph state for the document-processing agent."""

from langgraph.graph.message import MessagesState


class QState(MessagesState):
    document_chunks: list[str] | None = None
    questions: list[str] | None = None
    question_answers: str | None = None
    judged_answers: list[str] | None = None
    retry_count: int | None = None
    good_questions: list[str] | None = None
    check_questions: str | None = None
    bad_questions: dict[str, list] | None = None
    good_question_answers: list[str] | None = None
    quizz: list[str] | None = None
    query: str | None = None
