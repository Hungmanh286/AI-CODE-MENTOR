"""Schemas for the chat app."""

from pydantic import BaseModel, Field
from typing import Optional
from fastapi import status
from enum import Enum


class MessageName:
    agent = "agent"
    generate_agent = "generate_agent"
    pedagogical_agent = "pedagogical_agent"
    answer = "answer"
    feedback_agent = "feedback_agent"
    student_agent = "student_agent"


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
        ..., example="user", description="sender type. Must be in [user | bot]"
    )
    content: Optional[str] = Field("", example="hello", description="content message")
    type: ChatType = Field(..., example="stream", description="types of communication")
    session: Optional[str] = Field(
        None,
        example="51ad53a2-c365-4160-a669-51f5573b7236",
        description="chat session uuid",
    )
    trace_id: Optional[str] = Field(
        None,
        example="0107c2c0-4c8a-487c-ba42-bbc40e9cc654",
        description="question-answer trace id",
    )
    question_id: Optional[str] = Field(
        "",
        example="0107c2c0-4c8a-487c-ba42-bbc40e9cc654",
        description="received question id",
    )
    error_code: Optional[ErrorCode] = Field(
        ErrorCode.no_error, example=0, description="Response error code"
    )
