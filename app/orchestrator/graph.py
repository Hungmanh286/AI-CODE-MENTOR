"""Root LangGraph workflow: routes a conversation across the agent tools."""

import structlog
from langgraph.graph import END, START, StateGraph

from app.agents.common.state import State
from app.orchestrator.nodes import (
    answer_node,
    documents_node,
    tool_calls_node,
    tools_node,
)
from app.schemas import MessageName

logger = structlog.get_logger(__name__)


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
    workflow.add_edge("tools", END)
    # workflow.add_edge("documents_node", MessageName.answer)
    # workflow.add_edge(MessageName.answer, END)

    return workflow


if __name__ == "__main__":
    workflow = build_workflow()
    graph = workflow.compile()
    graph.get_graph().draw_mermaid_png(output_file_path="docs/assets/workflow.png")
