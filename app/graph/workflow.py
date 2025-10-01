import json
import uuid
from typing import Optional
from dotenv import load_dotenv
from fastapi import WebSocket
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables.config import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph

from app.graph.node import (
    tool_calls_node,
    tools_node,
    documents_node,
    answer_node,
)
from app.graph.state import State
from app.schema import ChatResponse, ChatType, Role, ErrorCode, UserToken, MessageName
from app.services import safe_send

load_dotenv()


def build_workflow():
    """Build langgraph workflow with structured routing and separate answer nodes."""
    workflow = StateGraph(State)

    nodes = {
        MessageName.agent: tool_calls_node,
        "tools": tools_node,
        "documents_node": documents_node,
        MessageName.answer: answer_node,
    }

    for node_name, action in nodes.items():
        workflow.add_node(node_name, action)

    workflow.add_edge(START, MessageName.agent)
    workflow.add_edge(MessageName.agent, "tools")
    workflow.add_edge("tools", "documents_node")
    # WARNING: Đặt "next_questions" sau "tools_node" sẽ không chạy song song
    workflow.add_edge("documents_node", MessageName.answer)
    workflow.add_edge("documents_node", MessageName.next_questions)
    workflow.add_edge(MessageName.answer, END)
    workflow.add_edge(MessageName.next_questions, END)

    return workflow


def suggest2str(suggest: str) -> str:
    """Validate suggest question in json format
    Args:
        suggest (str): llm response text
    Returns:
        str: suggestion if data is valid or empty array
    """
    try:
        data = str(suggest).replace("json", "").replace("`", "")
        if isinstance(json.loads(data), list):
            return data
        return "[]"
    except Exception:
        return "[]"


async def invoke_workflow(
    websocket: WebSocket,
    graph: CompiledStateGraph,
    message: str,
    session_uuid: str,
    question_id: str,
    user_token: UserToken,
    # tracer: CallbackHandler,
) -> None:
    _trace_id = str(uuid.uuid4())
    _question_id = question_id

    class SessionChatResponse(ChatResponse):
        session: str = session_uuid
        trace_id: str = _trace_id
        question_id: str = _question_id

    async def send_response(
        role: Role,
        content: str,
        msg_type: ChatType,
        error_code: Optional[ErrorCode] = None,
    ):
        resp = SessionChatResponse(
            role=role, content=content, type=msg_type, error_code=error_code
        )
        await safe_send(websocket, resp)

    config = RunnableConfig(
        configurable={
            "thread_id": f"{user_token.user_id}_{session_uuid}",
            "user_name": user_token.username,
            "user_id": user_token.user_id,
        },
        # callbacks=[tracer],
        metadata={
            "langfuse_user_id": user_token.user_id,
            "langfuse_session_id": session_uuid,
        },
        run_id=_trace_id,
    )

    await send_response(role=Role.user, content=message, msg_type=ChatType.stream)
    await send_response(role=Role.bot, content="", msg_type=ChatType.start)

    try:
        next_questions = ""
        prev_response_id = ""

        async for _, (msg, metadata) in graph.astream(
            input={"messages": [HumanMessage(content=message)]},
            config=config,
            stream_mode="messages",
            subgraphs=True,
        ):
            if not isinstance(msg, AIMessage) or not msg.content:
                continue

            node = metadata.get("langgraph_node", "")

            if MessageName.generate_agent in node:
                prev_response_id = prev_response_id or msg.id
                if msg.id != prev_response_id:
                    prev_response_id = msg.id
                    await send_response(
                        role=Role.bot, content="\n\n", msg_type=ChatType.stream
                    )
                await send_response(
                    role=Role.bot, content=msg.content, msg_type=ChatType.stream
                )

            if MessageName.next_questions in node:
                next_questions += msg.content

        await send_response(
            role=Role.bot,
            content=suggest2str(next_questions),
            msg_type=ChatType.suggest,
        )

    except Exception as e:
        print(f"session: {session_uuid}\nquestion: {message}\nerror: {e}")
        await send_response(
            role=Role.bot,
            content="An error occurred while creating the answer.",
            msg_type=ChatType.error,
            error_code=ErrorCode.server_error,
        )
    finally:
        await send_response(role=Role.bot, content="", msg_type=ChatType.end)
        # tracer.flush()


if __name__ == "__main__":
    workflow = build_workflow()
    graph = workflow.compile()
    # display(Image(graph.get_graph(xray=True).draw_mermaid_png()))
    graph.get_graph().draw_mermaid_png(output_file_path="graph.png")
