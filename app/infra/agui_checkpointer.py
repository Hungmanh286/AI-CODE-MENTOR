"""Checkpointer for the AG-UI agent (thread_id = session uuid = frontend threadId).

The AG-UI graph must NOT share checkpoint tables with the legacy WebSocket
graph: both use ``thread_id = session_uuid`` but have different nodes and
channels, so reading a legacy checkpoint with the new graph would resume
non-existent nodes. By default the checkpoints therefore live in their own
schema (``MENTOR_CHECKPOINT_SCHEMA``, default ``mentor_agui``) of the existing
checkpoint database (``CHECKPOINT_*`` settings). ``MENTOR_CHECKPOINT_DB_URL``
overrides the whole connection string (use a dedicated database there).

``AsyncPostgresSaver`` must be created inside the running event loop, so this
is an async context manager meant for the FastAPI lifespan.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

_SCHEMA_RE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def checkpoint_conninfo() -> tuple[str, str | None]:
    """Return ``(conninfo, schema)``; ``schema`` is None for an explicit URL."""
    if settings.MENTOR_CHECKPOINT_DB_URL:
        return settings.MENTOR_CHECKPOINT_DB_URL, None
    from psycopg.conninfo import make_conninfo

    schema = settings.MENTOR_CHECKPOINT_SCHEMA
    if not _SCHEMA_RE.match(schema or ""):
        raise ValueError(f"invalid MENTOR_CHECKPOINT_SCHEMA: {schema!r}")
    conninfo = make_conninfo(
        host=settings.CHECKPOINT_HOST,
        port=settings.CHECKPOINT_PORT,
        dbname=settings.CHECKPOINT_DB,
        user=settings.CHECKPOINT_USER,
        password=settings.CHECKPOINT_PASSWORD,
        options=f"-c search_path={schema}",
    )
    return conninfo, schema


@asynccontextmanager
async def agui_checkpointer() -> AsyncIterator[Any]:
    """Pooled ``AsyncPostgresSaver``; ``setup()`` is idempotent (creates 4 tables)."""
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import AsyncConnectionPool

    conninfo, schema = checkpoint_conninfo()
    # Same connection settings AsyncPostgresSaver.from_conn_string uses, but
    # pooled for concurrent requests.
    async with AsyncConnectionPool(
        conninfo=conninfo,
        max_size=settings.MENTOR_CHECKPOINT_POOL_SIZE,
        open=False,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    ) as pool:
        if schema:
            async with pool.connection() as conn:
                await conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
        saver = AsyncPostgresSaver(pool)
        await saver.setup()
        logger.info(f"AG-UI checkpointer ready (schema={schema or 'from URL'})")
        yield saver
