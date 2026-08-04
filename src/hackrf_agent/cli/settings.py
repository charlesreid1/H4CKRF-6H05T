"""Config file + keychain-backed secret storage.

One class: :class:`SettingsService`.  All keychain I/O goes through here.
"""

from __future__ import annotations

import contextlib
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import keyring

KEYRING_SERVICE: Final[str] = "hackrf-agent"
KEYRING_USERNAME: Final[str] = "openrouter-api-key"

DEFAULT_HOME: Final[Path] = Path.home() / ".hackrf-agent"


@dataclass(frozen=True)
class Settings:
    """Non-secret configuration held on disk in ~/.hackrf-agent/config.toml.

    Extend this dataclass, never the TOML shape, when adding new
    fields — the CLI knows only about these attributes; unknown TOML
    keys are ignored on load.
    """

    home_dir: Path
    model: str = "anthropic/claude-sonnet-5"
    max_history_messages: int = 24
    auto_approve_medium: bool = False


class SettingsService:
    """Reads ``~/.hackrf-agent/config.toml`` + the OS keychain.

    Does NOT create the file on first read — that's the doctor
    command's job. All fields fall back to defaults if the file
    is absent or malformed.
    """

    def __init__(self, home_dir: Path | None = None) -> None:
        self._home_dir = home_dir or DEFAULT_HOME

    @property
    def home_dir(self) -> Path:
        return self._home_dir

    @property
    def config_path(self) -> Path:
        return self._home_dir / "config.toml"

    @property
    def db_path(self) -> Path:
        return self._home_dir / "agent.db"

    @property
    def sessions_dir(self) -> Path:
        return self._home_dir / "sessions"

    def load(self) -> Settings:
        """Return the current settings, applying defaults for missing keys.

        Never raises on I/O errors — returns defaults if the file is
        missing or unreadable. A malformed TOML file logs a warning
        (via ``logging``) and returns defaults.
        """
        if not self.config_path.is_file():
            return Settings(home_dir=self._home_dir)
        try:
            with self.config_path.open("rb") as f:
                raw = tomllib.load(f)
        except (tomllib.TOMLDecodeError, OSError) as e:
            import logging

            logging.getLogger(__name__).warning("config.toml unreadable (%s); using defaults", e)
            return Settings(home_dir=self._home_dir)
        return Settings(
            home_dir=self._home_dir,
            model=str(raw.get("model", "anthropic/claude-sonnet-5")),
            max_history_messages=int(raw.get("max_history_messages", 24)),
            auto_approve_medium=bool(raw.get("auto_approve_medium", False)),
        )

    def save(self, settings: Settings) -> None:
        """Persist non-secret fields. Hand-rolls the TOML; keep tiny."""
        self._home_dir.mkdir(parents=True, exist_ok=True)
        content = (
            f'model = "{settings.model}"\n'
            f"max_history_messages = {settings.max_history_messages}\n"
            f"auto_approve_medium = {str(settings.auto_approve_medium).lower()}\n"
        )
        # Atomic-ish write: write to .tmp, rename.
        tmp = self.config_path.with_suffix(".toml.tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(self.config_path)

    # -- keychain -----------------------------------------------------------

    def get_api_key(self) -> str | None:
        """Return the stored API key, or None if not set."""
        return keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)

    def set_api_key(self, key: str) -> None:
        """Store the API key in the OS keychain. Overwrites any existing value."""
        if not key or not key.strip():
            raise ValueError("API key must be non-empty")
        keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, key.strip())

    def delete_api_key(self) -> None:
        """Remove the stored API key. Idempotent."""
        with contextlib.suppress(keyring.errors.PasswordDeleteError):
            keyring.delete_password(KEYRING_SERVICE, KEYRING_USERNAME)
