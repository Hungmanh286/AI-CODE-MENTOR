import sys

from langchain_core.runnables import RunnableLambda
from langgraph.graph import StateGraph, START, END
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


def build_pedagogical_workflow():
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

    return workflow


workflow = build_pedagogical_workflow()
pedagogical_expert_agent = workflow.compile()
