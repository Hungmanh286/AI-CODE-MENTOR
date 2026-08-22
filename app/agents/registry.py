"""The only place the orchestrator learns what the agents expose.

Add a new agent by exporting its tools from its package and listing them here;
nothing else in ``app/orchestrator`` needs to change.
"""

from app.agents.document_processing import (
    answer_tool,
    document_processing_tool,
    mindmap_tool,
    question_generation_tool,
    summary_tool,
)

AGENT_TOOLS = [
    document_processing_tool,
    mindmap_tool,
    answer_tool,
    question_generation_tool,
    summary_tool,
]

TOOLS_BY_NAME = {tool.name: tool for tool in AGENT_TOOLS}

__all__ = ["AGENT_TOOLS", "TOOLS_BY_NAME"]
