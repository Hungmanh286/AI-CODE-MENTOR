"""Structured-output schemas for the document-processing agent."""

from pydantic import BaseModel


class Question(BaseModel):
    """Schema for a single question"""

    id: str
    type: str
    difficulty: str
    question: str
    options: list[str]
    correct_answer: int  # Changed from str to int (0-3)
    explanation: str


class QuestionList(BaseModel):
    """Schema for list of selected questions"""

    selected_questions: list[Question]


class QuestionWithAnswer(BaseModel):
    """Schema for a single question with answer options"""

    id: int
    question: str
    options: list[str]  # List of 4 options starting with A., B., C., D.
    related_passage: str


class QuestionWithAnswerList(BaseModel):
    """Schema for list of questions with answers"""

    questions: list[QuestionWithAnswer]
