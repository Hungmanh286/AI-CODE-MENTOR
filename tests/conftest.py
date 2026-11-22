"""Pytest bootstrap: make the repository root importable as ``app``/``tests``."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _agent_auth_off_unless_a_test_turns_it_on(monkeypatch):
    """AGENT_AUTH_REQUIRED defaults to true; only the auth tests exercise it."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "AGENT_AUTH_REQUIRED", False)
