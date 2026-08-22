"""Compiled graph for the document-processing agent."""

import structlog
from langgraph.graph import END, START, StateGraph

from app.agents.document_processing.nodes import (
    answer_node,
    document_preprocessing,
    judge,
    question_node,
    should_continue,
    validate,
)
from app.agents.document_processing.state import QState

logger = structlog.get_logger(__name__)

workflow = StateGraph(QState)

workflow.add_node("document_preprocessing", document_preprocessing)
workflow.add_node("question_node", question_node)
workflow.add_node("answer_node", answer_node)
workflow.add_node("judge", judge)
workflow.add_node("validate", validate)

workflow.add_edge(START, "document_preprocessing")
workflow.add_edge("document_preprocessing", "question_node")
workflow.add_edge("question_node", "answer_node")
workflow.add_edge("answer_node", "judge")

workflow.add_conditional_edges(
    "judge", should_continue, {"question_node": "question_node", "end": "validate"}
)
workflow.add_edge("validate", END)

document_processing_agent = workflow.compile()


if __name__ == "__main__":
    from langchain_core.messages import HumanMessage
    from langfuse.langchain import CallbackHandler

    tracer = CallbackHandler()

    def print_stream(stream):
        for s in stream:
            logger.info(s)

    inputs = {"messages": [HumanMessage(content="Test")]}
    print_stream(
        document_processing_agent.stream(
            inputs, stream_mode="values", config={"callbacks": [tracer]}
        )
    )
