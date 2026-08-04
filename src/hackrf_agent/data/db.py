"""Connection factory and migration runner.

Nobody else opens a DB connection directly. Every component that needs
SQLite goes through ``open_connection`` or ``ensure_schema`` here.

* ``open_connection`` is an async context manager that yields a fresh
  ``aiosqlite`` connection with the project's standard PRAGMAs applied
  and closes it on exit.
* ``ensure_schema`` idempotently applies ``schema.sql`` and any pending
  additive migrations on startup.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.resources import files
from pathlib import Path
from typing import Final

import aiosqlite

SCHEMA_VERSION: Final[int] = 1
_SCHEMA_SQL_RESOURCE: Final[str] = "schema.sql"


@asynccontextmanager
async def open_connection(
    db_path: Path | str,
) -> AsyncIterator[aiosqlite.Connection]:
    """Async context manager that yields a ready *aiosqlite* connection.

    Usage::

        async with open_connection(db_path) as conn:
            async with conn.execute("SELECT ...") as cur:
                ...
    """
    conn = await aiosqlite.connect(db_path)
    await _apply_pragmas(conn)
    try:
        yield conn
    finally:
        await conn.close()


async def ensure_schema(db_path: Path | str) -> None:
    """Idempotently apply *schema.sql* and any pending migrations.

    Safe to call on every process startup.  A fresh DB gets tables created
    and ``PRAGMA user_version`` stamped to ``SCHEMA_VERSION``.  Subsequent
    calls are a no-op unless a migration is pending.
    """
    async with open_connection(db_path) as conn:
        current = await _get_user_version(conn)

        if current == 0:
            await _apply_schema_sql(conn)
            await conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION};")
            await conn.commit()
            return

        # Future migrations dispatch on *current* here.
        if current > SCHEMA_VERSION:
            raise RuntimeError(
                f"DB at {db_path} has user_version {current}, "
                f"newer than this binary ({SCHEMA_VERSION}). Refusing to open."
            )
        # current == SCHEMA_VERSION: no-op.


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _apply_pragmas(conn: aiosqlite.Connection) -> None:
    """Set WAL mode, reduced synchronous, and foreign-key enforcement."""
    await conn.execute("PRAGMA journal_mode = WAL;")
    await conn.execute("PRAGMA synchronous = NORMAL;")
    await conn.execute("PRAGMA foreign_keys = ON;")
    # aiosqlite defaults to auto-commit off; callers manage commits.


async def _get_user_version(conn: aiosqlite.Connection) -> int:
    """Read *PRAGMA user_version* from the open connection."""
    async with conn.execute("PRAGMA user_version;") as cur:
        row = await cur.fetchone()
        return int(row[0]) if row else 0


async def _apply_schema_sql(conn: aiosqlite.Connection) -> None:
    """Load and execute the bundled ``schema.sql``."""
    sql = files("hackrf_agent.data").joinpath(_SCHEMA_SQL_RESOURCE).read_text()
    await conn.executescript(sql)
