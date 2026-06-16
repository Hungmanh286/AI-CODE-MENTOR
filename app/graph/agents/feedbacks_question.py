import structlog

# con agent này

import sys

from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, START, END

from app.chatmodel import init_llm
from app.schema import MessageName
from app.graph.state import State
from app.config import settings


logger = structlog.get_logger(__name__)

TOOLS = []

try:
    llm = init_llm(
        model=settings.CHAT_MODEL,
        temperature=settings.CHAT_MODEL_TEMPERATURE,
        tags=["feedback_agent"],
    )

    llm_feedback = llm.bind_tools(TOOLS)
except Exception as e:
    logger.info(f"Fatal Error: Failed to initialize API agent model: {e}")
    sys.exit(1)


def call_model(state: State, config: RunnableConfig):
    response = llm_feedback.invoke(state["messages"], config)
    return {"messages": [response]}


def build_feedbacks_workflow():
    workflow = StateGraph(State)
    workflow.add_node(MessageName.feedbacks_question, call_model)
    workflow.add_node("tools_node", ToolNode(TOOLS))

    workflow.add_edge(START, MessageName.feedbacks_question)
    workflow.add_edge(MessageName.feedbacks_question, "tools_node")
    workflow.add_edge("tools_node", END)

    return workflow


workflow = build_feedbacks_workflow()
feedbacks_question = workflow.compile()


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
    print_stream(feedbacks_question.stream(inputs, stream_mode="values"))
