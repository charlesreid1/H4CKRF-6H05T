"""Tests for session.py — SessionPaths and new_session factory."""

import re
from pathlib import Path

from hackrf_agent.domain.session import SessionPaths, new_session


class TestNewSession:
    def test_creates_all_dirs(self, tmp_path: Path) -> None:
        """new_session(tmp_path) creates all four directories on disk."""
        sp = new_session(tmp_path)
        assert sp.root.is_dir()
        assert sp.iq_dir.is_dir()
        assert sp.summary_dir.is_dir()
        assert sp.log_dir.is_dir()

    def test_distinct_session_ids(self, tmp_path: Path) -> None:
        """Two new_session() calls produce distinct session_ids."""
        sp1 = new_session(tmp_path)
        sp2 = new_session(tmp_path)
        assert sp1.session_id != sp2.session_id

    def test_session_id_pattern(self, tmp_path: Path) -> None:
        """session_id matches YYYY-MM-DDThh-mm-ss_<6 hex chars>."""
        sp = new_session(tmp_path)
        pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}_[0-9a-f]{6}$"
        assert re.match(pattern, sp.session_id), f"unexpected session_id: {sp.session_id!r}"


class TestSessionPaths:
    def test_ensure_idempotent(self, tmp_path: Path) -> None:
        """ensure() called twice does not raise."""
        sp = SessionPaths(session_id="test", root=tmp_path / "sess")
        sp.ensure()
        # Second call should be a no-op.
        sp.ensure()
        assert sp.root.is_dir()

    def test_is_within_positive(self, tmp_path: Path) -> None:
        """is_within returns True for a path under root."""
        sp = SessionPaths(session_id="test", root=tmp_path / "sess")
        sp.ensure()
        child = sp.iq_dir / "x.iq"
        child.touch()
        assert sp.is_within(child) is True

    def test_is_within_traversal_defeated(self, tmp_path: Path) -> None:
        """is_within returns False for .. traversal."""
        sp = SessionPaths(session_id="test", root=tmp_path / "sess")
        sp.ensure()
        escape = sp.root / ".." / "escape"
        assert sp.is_within(escape) is False

    def test_is_within_etc_passwd(self, tmp_path: Path) -> None:
        """is_within returns False for /etc/passwd."""
        sp = SessionPaths(session_id="test", root=tmp_path / "sess")
        sp.ensure()
        assert sp.is_within(Path("/etc/passwd")) is False

    def test_new_iq_path_under_iq_dir(self, tmp_path: Path) -> None:
        """new_iq_path returns a path under iq_dir with .iq suffix."""
        sp = SessionPaths(session_id="test", root=tmp_path / "sess")
        sp.ensure()
        p = sp.new_iq_path("capture")
        assert p.parent == sp.iq_dir
        assert p.suffix == ".iq"

    def test_new_iq_path_distinct(self, tmp_path: Path) -> None:
        """Two new_iq_path calls in tight succession produce distinct paths."""
        sp = SessionPaths(session_id="test", root=tmp_path / "sess")
        sp.ensure()
        p1 = sp.new_iq_path()
        p2 = sp.new_iq_path()
        assert p1 != p2

    def test_root_matches_base_dir_plus_session_id(self, tmp_path: Path) -> None:
        """root is base_dir / session_id."""
        sp = new_session(tmp_path)
        assert sp.root == tmp_path / sp.session_id
