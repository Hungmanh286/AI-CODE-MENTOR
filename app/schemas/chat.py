"""Schemas for the chat app."""

from enum import Enum
from typing import Optional

from fastapi import status
from pydantic import BaseModel, Field


class MessageName:
    agent = "agent"
    generate_agent = "generate_agent"
    question_agent = "question_agent"
    student_agent = "student_agent"
    answer = "answer"
    next_questions = "next_questions"
    feedbacks_answer = "feedbacks_answer"
    feedbacks_question = "feedbacks_question"


class Role(str, Enum):
    user = "user"
    bot = "bot"


class ChatType(str, Enum):
    start = "start"
    end = "end"
    stream = "stream"
    error = "error"
    info = "info"
    suggest = "suggest"
    interrupt = "interrupt"


class ErrorCode(int, Enum):
    no_error = 0
    ratelimit_error = status.HTTP_429_TOO_MANY_REQUESTS
    request_error = status.HTTP_400_BAD_REQUEST
    openai_error = status.HTTP_502_BAD_GATEWAY
    server_error = status.HTTP_503_SERVICE_UNAVAILABLE


class ChatResponse(BaseModel):
    """Chat response schema."""

    role: Role = Field(
        ..., json_schema_extra={"example": "user"}, description="sender type. Must be in [user | bot]"
    )
    content: Optional[str] = Field("", json_schema_extra={"example": "hello"}, description="content message")
    type: ChatType = Field(..., json_schema_extra={"example": "stream"}, description="types of communication")
    session: Optional[str] = Field(
        None,
        json_schema_extra={"example": "51ad53a2-c365-4160-a669-51f5573b7236"},
        description="chat session uuid",
    )
    trace_id: Optional[str] = Field(
        None,
        json_schema_extra={"example": "0107c2c0-4c8a-487c-ba42-bbc40e9cc654"},
        description="question-answer trace id",
    )
    question_id: Optional[str] = Field(
        "",
        json_schema_extra={"example": "0107c2c0-4c8a-487c-ba42-bbc40e9cc654"},
        description="received question id",
    )
    error_code: Optional[ErrorCode] = Field(
        ErrorCode.no_error, json_schema_extra={"example": 0}, description="Response error code"
    )
