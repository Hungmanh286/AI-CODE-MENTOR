import sys
import json

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    ToolMessage,
    SystemMessage,
    trim_messages,
)
from langchain_core.runnables import RunnableLambda
from langchain_core.runnables.config import RunnableConfig
from langgraph.prebuilt import ToolNode

from app.chatmodel import init_llm
from app.graph.prompts import Prompts
from app.graph.state import (
    filter_message,
    get_conversation_messages,
    get_tool_messages,
    State,
)

from app.graph.agents import planner, researcher, tutor  # noqa
from app.graph.tools import developer_tool, researcher_tool, tutor_tool
from app.schema import MessageName
from app.config import settings


# agent tổng bên ngoài sẽ có các tool để chọn

TOOLS = [developer_tool, researcher_tool, tutor_tool]

try:
    # LLM: Generate answer
    llm = init_llm(
        api_key=settings.CHAT_MODEL_KEY,
        model=settings.CHAT_MODEL,
        temperature=settings.CHAT_MODEL_TEMPERATURE,
        tags=["toolcalls"],
    )

    # LLM: Tool choice
    llm_with_tools = llm.bind_tools(
        TOOLS,
        tool_choice=True,
    )


except Exception as e:
    print(f"Error initializing model: {e}")
    sys.exit(1)


# Step 1: Init model tool calls
async def tool_calls_node(state: State, config: RunnableConfig):
    """Generate tool call and determine routing."""
    conversation_messages = filter_message(state)

    response = await llm_with_tools.ainvoke(conversation_messages, config)
    response.name = MessageName.agent

    query = conversation_messages[-1].content if conversation_messages else ""

    try:
        tool_calls_kwargs = response.additional_kwargs

        if "tool_calls" in tool_calls_kwargs:
            arguments = json.loads(
                tool_calls_kwargs.get("tool_calls", [])[0]["function"]["arguments"]
            )
            query = arguments.get("query", "")
        elif "function_call" in tool_calls_kwargs:
            arguments = json.loads(tool_calls_kwargs["function_call"]["arguments"])
            query = arguments.get("query", "")
    except Exception:
        pass
    return {"messages": [response], "user_question": query}


# Step 2: Execute the tool.
def handle_tool_error(state: State) -> dict:
    """Function to handle errors that occur during tool execution."""
    error = state.get("error")
    tool_calls = state["messages"][-1].tool_calls
    return {
        "messages": [
            ToolMessage(
                content=f"Error: {repr(error)}\n.",
                tool_call_id=tc["id"],
            )
            for tc in tool_calls
        ]
    }


tools_node = ToolNode(TOOLS).with_fallbacks(
    [RunnableLambda(handle_tool_error)],
    exception_key="error",
)


# Step 3: Extract documents from tool messages
def documents_node(state: State) -> dict:
    """Add documents to state."""
    tool_messages = get_tool_messages(state=state)
    documents = []
    for t_message in tool_messages:
        if t_message.status == "error":
            continue
        if not t_message.content:  # Skip empty or None content
            continue
        try:
            data = json.loads(t_message.content)
            if isinstance(data, list):
                # Filter out None values from list
                documents.extend([item for item in data if item is not None])
            else:
                documents.append(data)
        except Exception:
            if isinstance(t_message.content, str):
                documents.append(t_message.content)

    return {"documents": documents}


# Step 4: Generate a response using the retrieved content.
async def answer_node(state: State, config: RunnableConfig):
    """Generate answer for questions."""
    user_name = config["configurable"].get("user_name", "")

    documents = state.get("documents", [])
    docs_content = []
    for c in documents:
        if c is None:  # Skip None values
            continue
        if isinstance(c, dict):
            page_content = c.get("page_content")
            if page_content is not None:
                docs_content.append(page_content)
            else:
                docs_content.append(str(c))
            continue
        if c:  # Only add non-empty values
            docs_content.append(str(c))

    # Join non-empty documents with separator
    if docs_content:
        docs_content = "\n\n---\n".join(docs_content)
    else:
        docs_content = "No relevant documents found."

    # Check if ANSWER_SYSTEM_PROMPT is empty and provide a default prompt if needed
    if Prompts.ANSWER_SYSTEM_PROMPT:
        system_prompt_content = Prompts.ANSWER_SYSTEM_PROMPT.format(
            docs_content=docs_content,
            user_name=user_name,
        )
    else:
        system_prompt_content = f"You are a helpful AI assistant for {user_name if user_name else 'the user'}. Answer questions based on the provided context."

    system_message = SystemMessage(content=system_prompt_content)

    # Create system context with document content
    context_prefix = "Use the following documents as context for your response:"
    system_context = SystemMessage(content=f"{context_prefix}\n\n{docs_content}")

    # Get conversation messages
    full_conversation_messages = get_conversation_messages(
        state, aimessage_name=[MessageName.answer]
    )
    conversation_messages = trim_messages(
        full_conversation_messages,
        strategy="last",
        token_counter=len,
        max_tokens=settings.HISTORY_CONTEXT_LEN,
        start_on=HumanMessage,
        end_on=(HumanMessage, AIMessage),
        include_system=False,
    )

    prompt = {"messages": [system_message] + [system_context] + conversation_messages}

    response_msg = await planner.ainvoke(prompt, config=config)
    content = response_msg["messages"][-1].content
    return {
        "messages": [AIMessage(content=content, name=MessageName.answer)],
        "ai_answer": content,
    }
