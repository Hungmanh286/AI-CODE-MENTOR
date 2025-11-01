from typing import List, TypedDict, Optional

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    ToolMessage,
    SystemMessage,
    trim_messages,
)
from langgraph.graph.message import MessagesState


from app.schema import MessageName
from app.config import settings


class Question(TypedDict):
    """A multi choice question."""

    question: str
    choices: List[str]
    answer: Optional[str]


class State(MessagesState):
    user_question: str | None
    ai_answer: str | None
    documents: List | None
    next: str | None
    file_path: str | None
    collection_name: str | None
    docs: List | None
    summarize_context: str | None
    evaluation_result: str | None
    questions: List[Question]
    selected_answers: List[str]


def get_conversation_messages(
    state: State, aimessage_name: List[str] = None
) -> List[BaseMessage]:
    """Remove tool messages and tool calls messages from state to reduce prompt size

    Args:
        state (State): state message
        aimessage_name (List[str]): list of message name to select. Default None is all

    Returns:
        List[BaseMessage]: conversation messages
    """
    conversation_messages = []
    for message in state["messages"]:
        if not message.content:
            continue
        if isinstance(message, (SystemMessage, HumanMessage)):
            conversation_messages.append(message)
        if isinstance(message, AIMessage) and not message.tool_calls:
            if aimessage_name is None or message.name in aimessage_name:
                conversation_messages.append(message)
    return conversation_messages


def get_tool_messages(state: State) -> List:
    """Get ToolMessages from previous node"""
    recent_tool_messages = []
    is_last_tool = isinstance(state["messages"][-1], ToolMessage)
    for message in reversed(state["messages"]):
        if isinstance(message, ToolMessage):
            recent_tool_messages.append(message)
            is_last_tool = True
            continue
        if is_last_tool and not isinstance(message, ToolMessage):
            break
    return recent_tool_messages[::-1]


def filter_message(
    state: State, last_n_message: int = settings.HISTORY_CONTEXT_LEN
) -> List:
    """Keep the last <= n_count tokens of the messages.

    Args:
        state (MessagesState): message history
        last_n_message (int, optional): history window length. Defaults to $settings.HISTORY_CONTEXT_LEN

    Returns:
        List: list of history message
    """
    conversation_messages = get_conversation_messages(
        state, aimessage_name=[MessageName.answer]
    )

    query_tool_messages = trim_messages(
        conversation_messages,
        strategy="last",
        token_counter=len,
        max_tokens=last_n_message,
        start_on=(SystemMessage, HumanMessage),
        end_on=(HumanMessage, AIMessage),
        include_system=True,
    )

    return query_tool_messages
