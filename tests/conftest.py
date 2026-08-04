"""Shared pytest configuration — marker gating + fixtures available to all tests.

The three tiers are ``unit``, ``integration``, ``e2e`` (directory layout).
``@pytest.mark.hardware`` and ``@pytest.mark.llm`` are *orthogonal* to the
tier — either can appear on integration or e2e tests. Unit tests never carry
either marker.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hackrf_agent.domain.session import SessionPaths, new_session

# ---------------------------------------------------------------------------
# CLI flags — opt-in tiers
# ---------------------------------------------------------------------------


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register --hardware and --llm CLI flags for opt-in tiers."""
    parser.addoption(
        "--hardware",
        action="store_true",
        default=False,
        help="Run tests marked @pytest.mark.hardware (requires HackRF attached).",
    )
    parser.addoption(
        "--llm",
        action="store_true",
        default=False,
        help="Run tests marked @pytest.mark.llm (requires ANTHROPIC_API_KEY).",
    )


# ---------------------------------------------------------------------------
# Auto-skip logic
# ---------------------------------------------------------------------------


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item],
) -> None:
    """Skip hardware/llm-marked tests unless the corresponding flag is set."""
    run_hardware = config.getoption("--hardware")
    run_llm = config.getoption("--llm")

    skip_hardware = pytest.mark.skip(reason="need --hardware to run")
    skip_llm = pytest.mark.skip(reason="need --llm to run")

    for item in items:
        if "hardware" in item.keywords and not run_hardware:
            item.add_marker(skip_hardware)
        if "llm" in item.keywords and not run_llm:
            item.add_marker(skip_llm)


# ---------------------------------------------------------------------------
# Enable pytester for self-testing conftest behaviour
# ---------------------------------------------------------------------------

pytest_plugins = ["pytester"]

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_session_paths(tmp_path: Path) -> SessionPaths:
    """A fresh SessionPaths rooted under pytest's tmp_path."""
    return new_session(tmp_path / "sessions")


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    """A per-test SQLite path; caller runs ensure_schema."""
    return tmp_path / "agent.db"


@pytest.fixture
def fake_driver():
    """The shared FakeDriver imported from tests/support/fake_driver.py."""
    from tests.support.fake_driver import FakeDriver

    return FakeDriver()


@pytest.fixture
def fake_llm_client():
    """A fresh FakeLLMClient with no responses queued; test populates it."""
    from hackrf_agent.ai.llm_client import FakeLLMClient

    return FakeLLMClient()


@pytest.fixture
def frozen_clock(monkeypatch: pytest.MonkeyPatch):
    """Freeze time.time() and time.monotonic() to configurable values.

    Yields a small object with .advance(seconds) and .set(t) methods.
    Tests that assert on timestamps or exercise TTL logic use this.
    """
    import time

    state = {"t": 1_000_000.0, "mono": 100.0}

    def _time() -> float:
        return state["t"]

    def _monotonic() -> float:
        return state["mono"]

    monkeypatch.setattr(time, "time", _time)
    monkeypatch.setattr(time, "monotonic", _monotonic)

    class _Clock:
        @staticmethod
        def advance(seconds: float) -> None:
            state["t"] += seconds
            state["mono"] += seconds

        @staticmethod
        def set(t: float) -> None:
            state["t"] = t
            state["mono"] = t

    yield _Clock()
