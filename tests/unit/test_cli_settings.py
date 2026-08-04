"""Unit tests for :mod:`hackrf_agent.cli.settings`."""

from __future__ import annotations

import pytest

from hackrf_agent.cli.settings import (
    Settings,
    SettingsService,
)


@pytest.fixture
def fake_keyring(monkeypatch):
    """Replace keyring.get_password / set_password / delete_password
    with an in-memory dict for the duration of the test.
    """
    store: dict[tuple[str, str], str] = {}

    def _get(service, user):
        return store.get((service, user))

    def _set(service, user, val):
        store[(service, user)] = val

    def _del(service, user):
        if (service, user) not in store:
            import keyring.errors

            raise keyring.errors.PasswordDeleteError("not found")
        del store[(service, user)]

    monkeypatch.setattr("keyring.get_password", _get)
    monkeypatch.setattr("keyring.set_password", _set)
    monkeypatch.setattr("keyring.delete_password", _del)
    return store


class TestSettingsServiceLoad:
    """Tests for SettingsService.load()."""

    def test_fresh_dir_returns_defaults(self, tmp_path) -> None:
        svc = SettingsService(home_dir=tmp_path)
        s = svc.load()
        assert s.model == "claude-sonnet-5"
        assert s.max_history_messages == 24
        assert s.auto_approve_medium is False
        assert s.home_dir == tmp_path

    def test_save_round_trip(self, tmp_path) -> None:
        svc = SettingsService(home_dir=tmp_path)
        orig = Settings(
            home_dir=tmp_path,
            model="claude-opus-4-8",
            max_history_messages=48,
            auto_approve_medium=True,
        )
        svc.save(orig)
        loaded = svc.load()
        assert loaded.model == "claude-opus-4-8"
        assert loaded.max_history_messages == 48
        assert loaded.auto_approve_medium is True

    def test_malformed_toml_returns_defaults(self, tmp_path) -> None:
        cfg = tmp_path / "config.toml"
        cfg.write_text("not = valid = toml")
        svc = SettingsService(home_dir=tmp_path)
        s = svc.load()
        assert s.model == "claude-sonnet-5"

    def test_missing_file_returns_defaults(self, tmp_path) -> None:
        svc = SettingsService(home_dir=tmp_path / "nonexistent")
        s = svc.load()
        assert s.model == "claude-sonnet-5"


class TestSettingsServiceKeychain:
    """Tests for SettingsService keychain methods."""

    def test_get_api_key_none_when_not_stored(self, tmp_path, fake_keyring) -> None:
        svc = SettingsService(home_dir=tmp_path)
        assert svc.get_api_key() is None

    def test_set_and_get_api_key(self, tmp_path, fake_keyring) -> None:
        svc = SettingsService(home_dir=tmp_path)
        svc.set_api_key("sk-fake")
        assert svc.get_api_key() == "sk-fake"

    def test_set_empty_api_key_raises(self, tmp_path, fake_keyring) -> None:
        svc = SettingsService(home_dir=tmp_path)
        with pytest.raises(ValueError, match="API key must be non-empty"):
            svc.set_api_key("")

    def test_set_whitespace_stripped(self, tmp_path, fake_keyring) -> None:
        svc = SettingsService(home_dir=tmp_path)
        svc.set_api_key("   sk-real   ")
        assert svc.get_api_key() == "sk-real"

    def test_delete_nonexistent_does_not_raise(self, tmp_path, fake_keyring) -> None:
        svc = SettingsService(home_dir=tmp_path)
        svc.delete_api_key()  # should not raise

    def test_delete_existing_key(self, tmp_path, fake_keyring) -> None:
        svc = SettingsService(home_dir=tmp_path)
        svc.set_api_key("sk-to-delete")
        svc.delete_api_key()
        assert svc.get_api_key() is None


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
