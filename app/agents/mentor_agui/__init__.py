"""AG-UI agent for the assistant-ui frontend (POST /agent, GET /threads/{id}/messages).

Contract: mentor-code-ui ``docs/agui/PLAN.md`` section 4. Ported from the
frontend repo's ``backend-reference/`` and checked by ``scripts/agui_selfcheck.py``.
"""

from app.agents.mentor_agui.agent import MentorLangGraphAgent, make_agent
from app.agents.mentor_agui.graph import build_graph
from app.agents.mentor_agui.history import get_thread_messages

__all__ = ["MentorLangGraphAgent", "build_graph", "get_thread_messages", "make_agent"]
