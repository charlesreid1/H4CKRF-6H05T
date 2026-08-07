"""Integration tests for the ``hackrf-agent lore`` CLI subcommand."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from hackrf_agent.cli.main import app


@pytest.fixture
def runner():
    return CliRunner()


class TestLoreList:
    def test_lists_topics(self, runner) -> None:
        result = runner.invoke(app, ["lore", "list"])
        assert result.exit_code == 0
        assert "dsp" in result.stdout
        assert "modulation" in result.stdout


class TestLoreRead:
    def test_reads_dsp_readme(self, runner) -> None:
        result = runner.invoke(app, ["lore", "read", "dsp", "README.md"])
        assert result.exit_code == 0
        assert len(result.stdout) > 0

    def test_rejects_missing_file(self, runner) -> None:
        result = runner.invoke(app, ["lore", "read", "dsp", "no-such.md"])
        assert result.exit_code != 0


class TestLoreSearch:
    def test_finds_manchester(self, runner) -> None:
        result = runner.invoke(app, ["lore", "search", "Manchester"])
        assert result.exit_code == 0
        assert "Manchester" in result.stdout or "hits" in result.stdout

    def test_no_match(self, runner) -> None:
        result = runner.invoke(
            app, ["lore", "search", "xyzzy-no-such-corpus-string-xyzzy"]
        )
        assert result.exit_code == 0
        assert "No matches" in result.stdout


class TestLoreLookupBand:
    def test_ism_433(self, runner) -> None:
        result = runner.invoke(app, ["lore", "lookup-band", "433920000"])
        assert result.exit_code == 0
        assert "band-ism-433" in result.stdout


class TestLoreLookupModulation:
    def test_ook(self, runner) -> None:
        result = runner.invoke(app, ["lore", "lookup-modulation", "OOK"])
        assert result.exit_code == 0
        assert "modulation-ook" in result.stdout

    def test_no_match(self, runner) -> None:
        result = runner.invoke(
            app, ["lore", "lookup-modulation", "not-a-real-modulation"]
        )
        assert result.exit_code != 0


class TestLoreLookupProtocol:
    def test_pocsag(self, runner) -> None:
        result = runner.invoke(app, ["lore", "lookup-protocol", "POCSAG"])
        assert result.exit_code == 0
        assert "pocsag" in result.stdout.lower()


class TestLoreLookupDecoder:
    def test_manchester(self, runner) -> None:
        result = runner.invoke(app, ["lore", "lookup-decoder", "Manchester"])
        assert result.exit_code == 0
        assert "manchester" in result.stdout.lower()


class TestLoreLookupKeyfob:
    def test_by_vendor(self, runner) -> None:
        result = runner.invoke(
            app, ["lore", "lookup-keyfob", "--vendor", "Chamberlain"]
        )
        assert result.exit_code == 0
        assert "chamberlain" in result.stdout.lower()

    def test_requires_a_hint(self, runner) -> None:
        result = runner.invoke(app, ["lore", "lookup-keyfob"])
        assert result.exit_code != 0
        assert "vendor" in result.stdout.lower() or "model" in result.stdout.lower()
