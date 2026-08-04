"""Tests for tests/conftest.py — marker gating + shared fixture behaviour."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from hackrf_agent.domain.session import SessionPaths

# ---------------------------------------------------------------------------
# Test 1: --hardware flag is registered
# ---------------------------------------------------------------------------


def test_hardware_flag_registered() -> None:
    """--hardware flag is a registered pytest option."""
    from tests.conftest import pytest_addoption

    # Build a mini parser and introspect.
    parser = pytest.Parser()
    pytest_addoption(parser)
    # Access the option group.
    group = parser._groups[0]
    options = {o.dest: o for o in group.options}
    assert "hardware" in options
    assert "llm" in options


# ---------------------------------------------------------------------------
# Test 2: @pytest.mark.hardware skipped without --hardware
# ---------------------------------------------------------------------------


@pytest.mark.skip(
    reason="requires subprocess invocation; covered by manual `pytest -m hardware` smoke test"
)
def test_hardware_marker_skipped_without_flag(pytester: pytest.Pytester) -> None:
    """A test marked @pytest.mark.hardware is skipped when --hardware is absent.

    Uses pytester to run a synthetic test file in a subprocess. The pytester
    fixture is provided by pytest's pytester plugin (conftest loads it via
    ``pytest_plugins = ["pytester"]``).
    """
    pytester.makepyfile("""
        import pytest

        @pytest.mark.hardware
        def test_hw():
            assert False, "should have been skipped"
    """)
    result = pytester.runpytest()
    # Without --hardware the test should be skipped.
    assert "test_hw" in result.stdout.str()
    assert "need --hardware" in result.stdout.str()
    assert result.ret == 0  # skip counts as pass


# ---------------------------------------------------------------------------
# Test 3: tmp_session_paths fixture yields valid SessionPaths
# ---------------------------------------------------------------------------


def test_tmp_session_paths_fixture(
    tmp_session_paths: SessionPaths,
) -> None:
    """tmp_session_paths yields a SessionPaths with root.exists() and valid session_id."""
    from hackrf_agent.domain.session import SessionPaths

    assert isinstance(tmp_session_paths, SessionPaths)
    assert tmp_session_paths.root.exists()
    assert tmp_session_paths.session_id
    # session_id format: ISO-timestamp_uuidhex
    assert re.match(
        r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}_[0-9a-f]{6}",
        tmp_session_paths.session_id,
    ), f"unexpected session_id format: {tmp_session_paths.session_id!r}"


# ---------------------------------------------------------------------------
# Additional: tmp_db fixture provides a Path
# ---------------------------------------------------------------------------


def test_tmp_db_fixture(tmp_db: Path) -> None:
    """tmp_db fixture yields a Path that does not yet exist (caller runs ensure_schema)."""
    assert isinstance(tmp_db, Path)
    assert not tmp_db.exists()  # Not created until ensure_schema runs.
