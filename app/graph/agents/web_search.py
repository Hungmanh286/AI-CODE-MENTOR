import sys

from langgraph.prebuilt import ToolNode
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langchain_community.tools import DuckDuckGoSearchRun


from app.chatmodel import init_llm
from app.graph.state import State
from app.schema import MessageName
from app.config import settings

search = DuckDuckGoSearchRun()

TOOLS = []

try:
    model = init_llm(
        api_key=settings.CHAT_MODEL_KEY,
        model=settings.CHAT_MODEL,
        temperature=settings.CHAT_MODEL_TEMPERATURE,
        tags=["student_agent"],
    )

    llm_student = model.bind_tools(TOOLS)
except Exception as e:
    print(f"Error initializing model: {e}")
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


workflow = StateGraph(State)
workflow.add_node(MessageName.student_agent, call_model)
workflow.add_node("generate_tools", ToolNode(TOOLS))
workflow.add_edge(START, MessageName.student_agent)
workflow.add_conditional_edges(
    MessageName.student_agent,
    should_continue,
    {
        "continue": "generate_tools",
        "end": END,
    },
)


student_agent = workflow.compile()


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
    print_stream(student_agent.stream(inputs, stream_mode="values"))
