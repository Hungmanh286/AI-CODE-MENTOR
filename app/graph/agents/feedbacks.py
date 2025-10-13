# con agent này

import sys

from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, START, END

from app.chatmodel import init_llm
from app.schema import MessageName
from app.graph.state import State
from app.config import settings

TOOLS = []

try:
    llm = init_llm(
        api_key=settings.CHAT_MODEL_KEY,
        model=settings.CHAT_MODEL,
        temperature=settings.CHAT_MODEL_TEMPERATURE,
        tags=["feedback_agent"],
    )

    llm_feedback = llm.bind_tools(TOOLS)
except Exception as e:
    print(f"Fatal Error: Failed to initialize API agent model: {e}")
    sys.exit(1)


def call_model(state: State, config: RunnableConfig):
    response = llm_feedback.invoke(state["messages"], config)
    return {"messages": [response]}


def build_feedbacks_workflow():
    workflow = StateGraph(State)
    workflow.add_node(MessageName.feedback_agent, call_model)
    workflow.add_node("any_tools", ToolNode(TOOLS))

    workflow.add_edge(START, MessageName.feedback_agent)
    workflow.add_edge(MessageName.feedback_agent, "any_tools")
    workflow.add_edge("any_tools", END)

    return workflow


workflow = build_feedbacks_workflow()
feedback_agent = workflow.compile()


if __name__ == "__main__":
    from langchain_core.messages import HumanMessage

    def print_stream(stream):
        for s in stream:
            message = s["messages"][-1]
            if isinstance(message, tuple):
                print(message)
            else:
                message.pretty_print()

    inputs = {"messages": [HumanMessage(content="4 nhân 9 bao nhiêu")]}
    print_stream(feedback_agent.stream(inputs, stream_mode="values"))
