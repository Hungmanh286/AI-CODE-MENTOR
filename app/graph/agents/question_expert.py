import uuid
import asyncio
import logging
import os


from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode, tools_condition  # noqa
from langchain_core.runnables.config import RunnableConfig
from langfuse.callback import CallbackHandler

from app.chatmodel import init_llm
from app.schema import MessageName
from app.config import settings


UPLOAD_DIR = "/tmp/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_latest_pdf_path(user_id, session_id):
    latest_file = os.path.join(UPLOAD_DIR, f"{user_id}_{session_id}_latest.txt")
    if os.path.exists(latest_file):
        with open(latest_file, "r") as f:
            return f.read().strip()
    return None


llm = init_llm(
    api_key=settings.CHAT_MODEL_KEY,
    model=settings.CHAT_MODEL,
    temperature=settings.CHAT_MODEL_TEMPERATURE,
    tags=["pdf_extractor_agent"],
)

client = MultiServerMCPClient(
    {
        "pdf_extractor": {
            "url": "http://localhost:8000/mcp",
            "transport": "streamable_http",
        }
    }
)

user_id = "demo_user"
session_uuid = str(uuid.uuid4())


async def run_agent_with_latest_pdf(user_id, session_uuid):
    _trace_id = str(uuid.uuid4())
    tracer = CallbackHandler(
        public_key="pk-lf-b483bf86-8746-4db0-a724-6938bb1d0d59",
        secret_key="sk-lf-a850ad25-a971-4483-909e-b3b2b64d4a2e",
        host="https://us.cloud.langfuse.com",
        tags=["question_expert"],
        metadata={
            "user_id ": user_id,
            "langfuse_session_id": session_uuid,
        },
    )

    tools = await client.get_tools()

    def call_model(state: MessagesState, config: RunnableConfig):
        logging.info("Calling LLM with messages: %s", state["messages"])
        return {"messages": llm.bind_tools(tools).invoke(state["messages"])}

    builder = StateGraph(MessagesState)

    builder.add_node(MessageName.question_agent, call_model)
    builder.add_node("tools_node", ToolNode(tools))
    builder.add_node("file_path", get_latest_pdf_path)

    builder.add_edge(START, MessageName.question_agent)
    builder.add_edge(MessageName.question_agent, "tools_node")
    builder.add_edge("tools_node", END)
    graph = builder.compile()

    config = RunnableConfig(
        configurable={
            "thread_id": f"{session_uuid}",
        },
        callbacks=[tracer],
        metadata={
            "langfuse_session_id": session_uuid,
        },
        run_id=_trace_id,
    )

    result = await graph.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": """Bạn là chuyên gia tạo câu hỏi cho người dùng hiểu được tất cả nội dung,hãy sử dụng tools phù hợp.
                    INnstruction: 
                    Bước 1 : trích xuất nội dung từ file pdf
                    Bước 2: Dựa vào nội dung đã trích xuất để tạo câu hỏi cho người dùng.
                    
                    """,
                }
            ]
        },
        config=config,
    )
    print("Final result:", result)
    tracer.flush()


# Ví dụ user_token truyền vào:
class UserToken:
    user_id = "demo_user"
    username = "Demo User"


if __name__ == "__main__":
    asyncio.run(run_agent_with_latest_pdf(UserToken()))
