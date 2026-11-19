"""AG-UI contract self-check (scripts/agui_selfcheck.py) as a unit test.

Offline: in-memory checkpointer, placeholder LLM hooks, no DB or network.
"""

import asyncio


def test_agui_selfcheck_passes_every_contract_check():
    from scripts import agui_selfcheck

    agui_selfcheck.RESULTS.clear()
    exit_code = asyncio.run(agui_selfcheck.main())
    failed = [(name, detail) for name, ok, detail in agui_selfcheck.RESULTS if not ok]
    assert exit_code == 0 and not failed, failed
    assert len(agui_selfcheck.RESULTS) >= 52
