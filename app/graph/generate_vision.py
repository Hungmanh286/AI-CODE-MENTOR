import structlog

import sys

from langgraph.prebuilt import ToolNode
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END

from app.chatmodel import init_llm
from app.graph.state import State
from app.schema import MessageName
from app.graph.tools import calculator_tool  # noqa

from app.config import settings


logger = structlog.get_logger(__name__)

TOOLS = []

try:
    model = init_llm(
        model=settings.CHAT_MODEL,
        temperature=settings.CHAT_MODEL_TEMPERATURE,
        tags=["agent"],
    )

    # TODO: bind tools if need
except Exception as e:
    logger.info(f"Error initializing model: {e}")
    sys.exit(1)


def call_model(state: State, config: RunnableConfig):
    response = model.invoke(state["messages"], config)
    return {"messages": [response]}


def should_continue(state: State):
    messages = state["messages"]
    last_message = messages[-1]
    if not last_message.tool_calls:
        return "end"
    else:
        return "continue"


def build_generate_workflow():
    workflow = StateGraph(State)
    workflow.add_node(MessageName.generate_agent, call_model)
    workflow.add_node("generate_tools", ToolNode(TOOLS))
    workflow.add_edge(START, MessageName.generate_agent)
    workflow.add_conditional_edges(
        MessageName.generate_agent,
        should_continue,
        {
            "continue": "generate_tools",
            "end": END,
        },
    )
    workflow.add_edge("generate_tools", MessageName.generate_agent)
    return workflow


workflow = build_generate_workflow()
generate_agent = workflow.compile()


if __name__ == "__main__":
    from langchain_core.messages import HumanMessage

    def print_stream(stream):
        for s in stream:
            message = s["messages"][-1]
            if isinstance(message, tuple):
                logger.info(message)
            else:
                message.pretty_print()

    inputs = {"messages": [HumanMessage(content="4 nhân 9 bao nhiêu")]}
    print_stream(generate_agent.stream(inputs, stream_mode="values"))
