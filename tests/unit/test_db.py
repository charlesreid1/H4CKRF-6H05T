"""Unit tests for ``hackrf_agent.data.db`` — connection factory and migration runner."""

import pytest

from hackrf_agent.data.db import SCHEMA_VERSION, ensure_schema, open_connection


class TestEnsureSchemaFresh:
    """Tests against a fresh (non-existent) database file."""

    async def test_creates_file_and_stamps_version(self, tmp_path):
        """ensure_schema on a fresh path creates the file and sets user_version."""
        db = tmp_path / "a.db"
        assert not db.exists()

        await ensure_schema(db)

        assert db.exists()
        async with open_connection(db) as conn:
            async with conn.execute("PRAGMA user_version;") as cur:
                ver = (await cur.fetchone())[0]
            assert ver == SCHEMA_VERSION

    async def test_idempotent(self, tmp_path):
        """Calling ensure_schema twice on the same path is a no-op."""
        db = tmp_path / "a.db"
        await ensure_schema(db)
        await ensure_schema(db)  # second call — must not raise

        async with open_connection(db) as conn:
            async with conn.execute("PRAGMA user_version;") as cur:
                ver = (await cur.fetchone())[0]
            assert ver == SCHEMA_VERSION

    async def test_wal_mode(self, tmp_path):
        """After ensure_schema, PRAGMA journal_mode returns 'wal'."""
        db = tmp_path / "a.db"
        await ensure_schema(db)

        async with open_connection(db) as conn:
            async with conn.execute("PRAGMA journal_mode;") as cur:
                mode = (await cur.fetchone())[0]
            assert mode == "wal"

    async def test_foreign_keys_on(self, tmp_path):
        """PRAGMA foreign_keys is ON on a freshly opened connection."""
        db = tmp_path / "a.db"
        await ensure_schema(db)

        async with open_connection(db) as conn:
            async with conn.execute("PRAGMA foreign_keys;") as cur:
                fk = (await cur.fetchone())[0]
            assert fk == 1

    async def test_tables_exist(self, tmp_path):
        """Both audit and grants tables exist after ensure_schema."""
        db = tmp_path / "a.db"
        await ensure_schema(db)

        async with open_connection(db) as conn:  # noqa: SIM117
            async with conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
            ) as cur:
                tables = {row[0] for row in await cur.fetchall()}

        assert "audit" in tables
        assert "grants" in tables


class TestEnsureSchemaVersionGuard:
    """Tests for the version-guard behaviour."""

    async def test_newer_version_raises(self, tmp_path):
        """If the DB has user_version newer than this binary, raise RuntimeError."""
        db = tmp_path / "a.db"

        # Manually create a DB with a bumped version number.
        import sqlite3

        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE IF NOT EXISTS dummy(x);")
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1};")
        conn.commit()
        conn.close()

        with pytest.raises(RuntimeError, match="newer than this binary"):
            await ensure_schema(db)
