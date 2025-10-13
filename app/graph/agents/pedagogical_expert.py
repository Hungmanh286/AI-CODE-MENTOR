import sys
import asyncio

from langchain_core.runnables import RunnableLambda
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage
from langfuse.langchain import CallbackHandler
from langgraph.prebuilt import ToolNode
from functools import partial

from app.chatmodel import init_llm
from app.schema import MessageName
from app.graph.state import State
from app.graph.tools import retriever_tool
from app.config import settings
from app.graph.node import (
    documents_node,
    tool_calls_node,
    answer_node,
    handle_tool_error,
)
from app.graph.prompts import Prompts


langfuse_handler = CallbackHandler()

TOOLS = [retriever_tool]


try:
    llm = init_llm(
        api_key=settings.CHAT_MODEL_KEY,
        model=settings.CHAT_MODEL,
        temperature=settings.CHAT_MODEL_TEMPERATURE,
        tags=["pedagogical_expert"],
    )
    llm_pedagogical = llm.bind_tools(TOOLS)
except Exception as e:
    print(f"Fatal Error: Failed to initialize API agent model: {e}")
    sys.exit(1)


tools_node = ToolNode(TOOLS).with_fallbacks(
    [RunnableLambda(handle_tool_error)],
    exception_key="error",
)

system_prompt_content = Prompts.PEDAGOGICAL_SYSTEM_PROMPTS

workflow = StateGraph(State)
workflow.add_node(MessageName.pedagogical_agent, tool_calls_node)
workflow.add_node("tools_node", tools_node)
workflow.add_node("document_node", documents_node)
workflow.add_node(
    "answer_node", partial(answer_node, system_prompt_content=system_prompt_content)
)

workflow.add_edge(START, MessageName.pedagogical_agent)
workflow.add_edge(MessageName.pedagogical_agent, "tools_node")
workflow.add_edge("tools_node", "document_node")
workflow.add_edge("document_node", "answer_node")
workflow.add_edge("answer_node", END)

pedagogical_expert_agent = workflow.compile()


def print_stream(stream):
    for s in stream:
        messages = s.get("messages", [])
        if not messages:
            continue
        message = messages[-1]
        try:
            message.pretty_print()
        except AttributeError:
            print(message)


async def main():
    user_input = input("Nhập nội dung hoặc từ khóa bài học: ")
    inputs = {"messages": [HumanMessage(content=user_input)]}

    config = RunnableConfig(tags=["pedagogical_expert_agent"])

    async for msg in pedagogical_expert_agent.astream(
        inputs,
        config={**config, "callbacks": [langfuse_handler]},
        stream_mode="messages",
    ):
        # Lấy ra content từ message
        if hasattr(msg, "content"):
            print("Nội dung trả về:", msg.content)
        else:
            print(msg)


if __name__ == "__main__":
    asyncio.run(main())
