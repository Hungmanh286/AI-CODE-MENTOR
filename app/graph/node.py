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
from app.graph.state import (
    filter_message,
    get_conversation_messages,
    get_tool_messages,
    State,
)
from app.graph.generate import generate_agent

from app.graph.agents.document_processing import (
    document_processing_tool,
    mindmap_tool,
    answer_tool,
    question_generation_tool,
    summary_tool,
)
from app.graph.prompts import Prompts
from app.schema import MessageName
from app.config import settings
# from app.graph.tools import retriever_tool

TOOLS = [
    document_processing_tool,
    mindmap_tool,
    answer_tool,
    question_generation_tool,
    summary_tool,
]

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
    user_query = conversation_messages[-1].content if conversation_messages else ""
    prompt_tool_choice = f"""Bạn là một trợ lý AI thông minh. Nhiệm vụ của bạn là chọn đúng công cụ để xử lý yêu cầu của người dùng.

DANH SÁCH CÔNG CỤ:
1. `using_to_create_questions_for_document`: Tạo câu hỏi trắc nghiệm TOÀN DIỆN từ toàn bộ tài liệu (xử lý chậm, đầy đủ, có đánh giá chất lượng).
2. `question_generation_tool`: Tạo câu hỏi trắc nghiệm NHANH từ chương/phần cụ thể trong tài liệu (xử lý nhanh, tập trung vào một phần).
3. `mindmap_tool`:  Tạo mind map.
4. `answer_tool`: Trả lời câu hỏi, giải thích, hỏi đáp thông thường từ tài liệu.
5. "summary_tool": Tóm tắt nội dung tài liệu.

Yêu cầu của người dùng: "{user_query}"

QUY TẮC LỰA CHỌN:
- Nếu yêu cầu "mind map", "bản đồ tư duy" → Chọn `mindmap_tool`
- Nếu yêu cầu "tạo câu hỏi từ TOÀN BỘ tài liệu", "quiz toàn diện", "bài kiểm tra đầy đủ", "tạo câu hỏi", nếu bạn khó xác định mặc định dùng tool này → Chọn `using_to_create_questions_for_document`
- Nếu yêu cầu "tạo câu hỏi về CHƯƠNG X", "quiz về PHẦN Y", "câu hỏi nhanh từ đoạn Z" → Chọn `question_generation_tool`
- Nếu yêu cầu "tóm tắt tài liệu", "tóm tắt nội dung", "tổng hợp" → Chọn `summary_tool`
- Nếu là câu hỏi thông thường, giải thích, hỏi đáp, hoặc không rõ ràng → Chọn `answer_tool`

PHÂ
N BIỆT QUAN TRỌNG:
- `using_to_create_questions_for_document`: Xử lý TOÀN BỘ tài liệu, có quy trình đánh giá chất lượng, tốn thời gian.
- `question_generation_tool`: Xử lý NHANH từ một PHẦN cụ thể, phù hợp khi người dùng chỉ định chương/phần.

Nếu không chắc chắn, mặc định sử dụng `answer_tool`."""
    response = await llm_with_tools.ainvoke(
        [HumanMessage(content=prompt_tool_choice)], config
    )
    response.name = MessageName.agent
    query = user_query
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
async def answer_node(
    state: State, config: RunnableConfig, system_prompt_content: Prompts = None
):
    """Generate answer for questions."""

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

    response_msg = await generate_agent.ainvoke(prompt, config=config)
    content = response_msg["messages"][-1].content
    return {
        "messages": [AIMessage(content=content, name=MessageName.answer)],
        "ai_answer": content,
    }


# Step 5: Generate next questions
async def next_questions_node(state: State, config: RunnableConfig):
    """Find next question from user query using FAQ retriever, fallback to documents."""

    related_questions = "abc"

    candidate_questions = (
        "\n".join([f"- {q.strip()}" for q in set(related_questions) if q.strip()])
        or "[]"
    )

    full_conversation_messages = get_conversation_messages(state, aimessage_name=[])
    conversation_messages = trim_messages(
        full_conversation_messages,
        strategy="last",
        token_counter=len,
        max_tokens=settings.HISTORY_CONTEXT_LEN,
        start_on=HumanMessage,
        end_on=HumanMessage,
        include_system=False,
    )
    conversation_questions = [msg.content for msg in conversation_messages]
    last_questions = (
        "\n".join([f"- {q.strip()}" for q in set(conversation_questions) if q.strip()])
        or "[]"
    )

    nextquestion_system_prompt = "Hãy gợi ý các câu hỏi tiếp theo"
    system_message_content = nextquestion_system_prompt.format(
        candidate_questions=candidate_questions, last_questions=last_questions
    )
    llm_questions = llm.model_copy(update={"tags": ["questions"]})

    prompt = [HumanMessage(system_message_content)]
    response = await llm_questions.ainvoke(prompt, config=config)
    response.name = MessageName.next_questions
    return {"messages": [response]}
