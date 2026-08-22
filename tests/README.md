# tests/

| Folder | What belongs here | Needs |
| --- | --- | --- |
| `unit/` | Pure logic + structural guards (imports, prompt split, dependency rule, security helpers). No network, no database. Must run in CI. | nothing |
| `integration/` | Agents and pipelines against real LLM / MinIO / Postgres. | `.env`, running infra |
| `e2e/` | Drives the HTTP/WebSocket API of a running service. | app running on `:8686` |
| `fixtures/` | Shared prompts, sample payloads, factories. | — |

Most files under `integration/` and `e2e/` are still manual scripts (`python tests/e2e/test_ask_api.py`)
rather than pytest cases — convert them as you touch them.

Run the fast suite (162 tests, ~10s, no backend needed):

```bash
uv run pytest tests/unit -q
```

`tests/unit/test_structure.py` is the guard rail for the layout: it fails if a module
stops importing, a `Prompts.X` / `settings.X` reference breaks, a package `__all__`
lists something missing, an agent starts importing `app.api`, or an absolute path
gets hardcoded. Run it after every move or rename.
