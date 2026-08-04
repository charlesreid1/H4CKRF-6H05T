"""Unit tests for :mod:`hackrf_agent.cli.settings`."""

from __future__ import annotations

from hackrf_agent.cli.settings import (
    ENV_API_KEY,
    Settings,
    SettingsService,
)
from hackrf_agent.ai.llm_client import DEFAULT_MODEL


class TestSettingsServiceLoad:
    """Tests for SettingsService.load()."""

    def test_fresh_dir_returns_defaults(self, tmp_path) -> None:
        svc = SettingsService(home_dir=tmp_path)
        s = svc.load()
        assert s.model == DEFAULT_MODEL
        assert s.max_history_messages == 24
        assert s.auto_approve_medium is False
        assert s.home_dir == tmp_path

    def test_save_round_trip(self, tmp_path) -> None:
        svc = SettingsService(home_dir=tmp_path)
        orig = Settings(
            home_dir=tmp_path,
            model="anthropic/claude-opus-4-8",
            max_history_messages=48,
            auto_approve_medium=True,
        )
        svc.save(orig)
        loaded = svc.load()
        assert loaded.model == "anthropic/claude-opus-4-8"
        assert loaded.max_history_messages == 48
        assert loaded.auto_approve_medium is True

    def test_malformed_toml_returns_defaults(self, tmp_path) -> None:
        cfg = tmp_path / "config.toml"
        cfg.write_text("not = valid = toml")
        svc = SettingsService(home_dir=tmp_path)
        s = svc.load()
        assert s.model == DEFAULT_MODEL

    def test_missing_file_returns_defaults(self, tmp_path) -> None:
        svc = SettingsService(home_dir=tmp_path / "nonexistent")
        s = svc.load()
        assert s.model == DEFAULT_MODEL


class TestSettingsServiceApiKey:
    """Tests for SettingsService.get_api_key()."""

    def test_get_api_key_none_when_env_unset(self, tmp_path, monkeypatch) -> None:
        monkeypatch.delenv(ENV_API_KEY, raising=False)
        svc = SettingsService(home_dir=tmp_path)
        assert svc.get_api_key() is None

    def test_get_api_key_returns_env(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv(ENV_API_KEY, "sk-from-env")
        svc = SettingsService(home_dir=tmp_path)
        assert svc.get_api_key() == "sk-from-env"

    def test_get_api_key_empty_env_is_none(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv(ENV_API_KEY, "")
        svc = SettingsService(home_dir=tmp_path)
        assert svc.get_api_key() is None

    def test_get_api_key_strips_whitespace(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv(ENV_API_KEY, "   sk-padded   ")
        svc = SettingsService(home_dir=tmp_path)
        assert svc.get_api_key() == "sk-padded"

    def test_get_api_key_whitespace_only_is_none(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv(ENV_API_KEY, "   \t  ")
        svc = SettingsService(home_dir=tmp_path)
        assert svc.get_api_key() is None

    def test_dotenv_file_loaded_from_cwd(self, tmp_path, monkeypatch) -> None:
        """A .env file in CWD populates the env var when it isn't already set."""
        monkeypatch.delenv(ENV_API_KEY, raising=False)
        cwd = tmp_path / "proj"
        cwd.mkdir()
        (cwd / ".env").write_text(f"{ENV_API_KEY}=sk-from-dotenv\n")
        monkeypatch.chdir(cwd)
        svc = SettingsService(home_dir=tmp_path / "home")
        assert svc.get_api_key() == "sk-from-dotenv"

    def test_env_var_wins_over_dotenv(self, tmp_path, monkeypatch) -> None:
        """An already-set env var is not overridden by .env — protects
        against a stale .env silently shadowing an intentional override.
        """
        cwd = tmp_path / "proj"
        cwd.mkdir()
        (cwd / ".env").write_text(f"{ENV_API_KEY}=sk-from-dotenv\n")
        monkeypatch.chdir(cwd)
        monkeypatch.setenv(ENV_API_KEY, "sk-from-real-env")
        svc = SettingsService(home_dir=tmp_path / "home")
        assert svc.get_api_key() == "sk-from-real-env"


class TestSettingsServicePaths:
    """Tests for SettingsService path properties."""

    def test_db_path_in_home_dir(self, tmp_path) -> None:
        svc = SettingsService(home_dir=tmp_path)
        assert svc.db_path == tmp_path / "agent.db"

    def test_sessions_dir_in_home_dir(self, tmp_path) -> None:
        svc = SettingsService(home_dir=tmp_path)
        assert svc.sessions_dir == tmp_path / "sessions"

    def test_config_path_in_home_dir(self, tmp_path) -> None:
        svc = SettingsService(home_dir=tmp_path)
        assert svc.config_path == tmp_path / "config.toml"
