"""Integration tests for the ``audit tail`` subcommand."""

from __future__ import annotations

import asyncio
import time
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from hackrf_agent.cli.main import app
from hackrf_agent.data.db import ensure_schema
from hackrf_agent.domain.audit_service import AuditService
from hackrf_agent.domain.models import (
    AuditEvent,
    AuditEventType,
    CommandAction,
    RiskLevel,
)


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def home(tmp_path):
    return tmp_path / "home"


async def _seed(db_path, session_id: str = "s1", count: int = 3) -> None:
    """Insert *count* audit rows via AuditService."""
    async with AuditService(db_path) as audit:
        for _ in range(count):
            await audit.log(
                AuditEvent(
                    trace_id=uuid4(),
                    session_id=session_id,
                    timestamp=time.time(),
                    event=AuditEventType.COMMAND_RECEIVED,
                    action=CommandAction.GET_DEVICE_INFO,
                    risk_level=RiskLevel.LOW,
                )
            )


class TestAuditTail:
    """Tests for ``audit tail``."""

    def test_empty_db(self, runner, home) -> None:
        result = runner.invoke(
            app,
            ["--home-dir", str(home), "audit", "tail"],
        )
        assert result.exit_code == 0
        assert "No audit rows match" in result.stdout

    def test_seeded_rows_appear(self, runner, home) -> None:
        # Seed the DB directly.
        home.mkdir(parents=True, exist_ok=True)
        db = home / "agent.db"
        asyncio.run(ensure_schema(db))
        asyncio.run(_seed(db, session_id="s1", count=3))

        result = runner.invoke(
            app,
            ["--home-dir", str(home), "audit", "tail"],
        )
        assert result.exit_code == 0, result.stderr
        assert "COMMAND_RECEIVED" in result.stdout

    def test_session_filter(self, runner, home) -> None:
        home.mkdir(parents=True, exist_ok=True)
        db = home / "agent.db"
        asyncio.run(ensure_schema(db))
        asyncio.run(_seed(db, session_id="s1", count=2))
        asyncio.run(_seed(db, session_id="s2", count=1))

        result = runner.invoke(
            app,
            ["--home-dir", str(home), "audit", "tail", "--session", "s1"],
        )
        assert result.exit_code == 0, result.stderr
        # All rows should be from s1 (2 rows).
        assert "COMMAND_RECEIVED" in result.stdout

    def test_bad_trace_uuid(self, runner, home) -> None:
        result = runner.invoke(
            app,
            ["--home-dir", str(home), "audit", "tail", "--trace", "deadbeef"],
        )
        assert result.exit_code == 2

    def test_limit(self, runner, home) -> None:
        home.mkdir(parents=True, exist_ok=True)
        db = home / "agent.db"
        asyncio.run(ensure_schema(db))
        asyncio.run(_seed(db, session_id="s1", count=10))

        result = runner.invoke(
            app,
            ["--home-dir", str(home), "audit", "tail", "--limit", "3"],
        )
        assert result.exit_code == 0, result.stderr
        # Should show exactly 3 rows.
        assert "last 3 rows" in result.stdout
