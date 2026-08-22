"""Every agent graph is wired correctly and the registry matches what it exposes."""

import inspect

import pytest

from app.agents.document_processing import document_processing_agent
from app.agents.document_processing import nodes as dp_nodes
from app.agents.feedback_answer import feedbacks_answer
from app.agents.feedback_question import feedbacks_question
from app.agents.generator import generate_agent
from app.agents.mindmap import summarize_agent
from app.agents.question_expert import question_agent
from app.agents.registry import AGENT_TOOLS, TOOLS_BY_NAME
from app.agents.summarizer import pdf_summarize_agent
from app.agents.web_search import student_agent
from app.orchestrator import build_workflow, invoke_workflow
from app.orchestrator import nodes as orchestrator_nodes

AGENTS = {
    "document_processing": document_processing_agent,
    "question_expert": question_agent,
    "mindmap": summarize_agent,
    "summarizer": pdf_summarize_agent,
    "feedback_answer": feedbacks_answer,
    "feedback_question": feedbacks_question,
    "web_search": student_agent,
    "generator": generate_agent,
}


@pytest.mark.parametrize("name", sorted(AGENTS))
def test_agent_graph_has_no_orphan_or_dead_end(name):
    graph = AGENTS[name].get_graph()
    targets = {edge.target for edge in graph.edges} | {"__start__"}
    sources = {edge.source for edge in graph.edges} | {"__end__"}
    assert [n for n in graph.nodes if n not in targets] == [], "node không ai trỏ tới"
    assert [n for n in graph.nodes if n not in sources] == [], "node không dẫn đi đâu"


def test_document_processing_wiring():
    edges = {(e.source, e.target) for e in document_processing_agent.get_graph().edges}
    assert {
        ("__start__", "document_preprocessing"),
        ("document_preprocessing", "question_node"),
        ("question_node", "answer_node"),
        ("answer_node", "judge"),
        ("judge", "question_node"),
        ("judge", "validate"),
        ("validate", "__end__"),
    } <= edges


def test_root_workflow_compiles():
    nodes = set(build_workflow().compile().get_graph().nodes)
    assert {"agent", "tools", "answer", "documents_node"} <= nodes


def test_invoke_workflow_signature_is_stable():
    assert list(inspect.signature(invoke_workflow).parameters) == [
        "websocket", "graph", "message", "session_uuid", "question_id", "user_token", "tracer",
    ]


@pytest.mark.parametrize("tool", AGENT_TOOLS, ids=lambda t: t.name)
def test_registry_tool_is_usable(tool):
    assert tool.name and tool.description
    assert tool.coroutine or tool.func
    assert "query" in tool.args_schema.model_json_schema()["properties"]


def test_registry_has_no_duplicate_names():
    assert len(TOOLS_BY_NAME) == len(AGENT_TOOLS)


def test_orchestrator_binds_exactly_the_registry():
    assert orchestrator_nodes.TOOLS is AGENT_TOOLS


@pytest.mark.parametrize(
    "module,name",
    [(dp_nodes, n) for n in ("document_preprocessing", "question_node", "answer_node", "judge", "validate")]
    + [(orchestrator_nodes, n) for n in ("tool_calls_node", "documents_node", "answer_node")],
)
def test_node_takes_state_first(module, name):
    assert list(inspect.signature(getattr(module, name)).parameters)[0] == "state"


@pytest.mark.parametrize(
    "state,expected",
    [
        ({"bad_questions": {f"c{i}": ["q"] for i in range(25)}, "retry_count": 0}, "question_node"),
        ({"bad_questions": {f"c{i}": ["q"] for i in range(25)}, "retry_count": 99}, "end"),
        ({"bad_questions": {"c1": ["q"]}, "retry_count": 0}, "end"),
        ({"bad_questions": {}, "retry_count": 0}, "end"),
        ({"retry_count": 0}, "end"),  # state thiếu key (resume checkpoint) không được crash
    ],
)
def test_should_continue(state, expected):
    assert dp_nodes.should_continue({"messages": [], **state}) == expected
