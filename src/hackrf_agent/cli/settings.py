"""Config file + environment-backed secret storage.

One class: :class:`SettingsService`.  The OpenRouter API key is read
from the ``OPENROUTER_API_KEY`` environment variable, with support
for loading a ``.env`` file from the current working directory (via
``python-dotenv``) so contributors can drop credentials in a
git-ignored file next to the repo.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from dotenv import load_dotenv

from hackrf_agent.ai.llm_client import DEFAULT_MODEL

ENV_API_KEY: Final[str] = "OPENROUTER_API_KEY"

DEFAULT_HOME: Final[Path] = Path.home() / ".hackrf-agent"


@dataclass(frozen=True)
class Settings:
    """Non-secret configuration held on disk in ~/.hackrf-agent/config.toml.

    Extend this dataclass, never the TOML shape, when adding new
    fields — the CLI knows only about these attributes; unknown TOML
    keys are ignored on load.
    """

    home_dir: Path
    model: str = DEFAULT_MODEL
    max_history_messages: int = 24
    auto_approve_medium: bool = False


class SettingsService:
    """Reads ``~/.hackrf-agent/config.toml`` + the ``OPENROUTER_API_KEY`` env var.

    Does NOT create the file on first read — that's the doctor
    command's job. All fields fall back to defaults if the file
    is absent or malformed.

    On construction, loads variables from a ``.env`` file in the
    current working directory (if present) into ``os.environ`` without
    overriding values already set. This lets contributors keep their
    key in a git-ignored ``.env`` alongside the project.
    """

    def __init__(self, home_dir: Path | None = None) -> None:
        self._home_dir = home_dir or DEFAULT_HOME
        # Load a `.env` sitting next to CWD (project root, typically). Do
        # not walk upward — that would silently pick up a stray .env in a
        # parent directory. Pre-existing env vars always win.
        dotenv_path = Path.cwd() / ".env"
        if dotenv_path.is_file():
            load_dotenv(dotenv_path=dotenv_path, override=False)

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
            model=str(raw.get("model", DEFAULT_MODEL)),
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

    # -- api key ------------------------------------------------------------

    def get_api_key(self) -> str | None:
        """Return the ``OPENROUTER_API_KEY`` env var, stripped.

        Returns ``None`` when the variable is unset or empty after
        stripping whitespace.
        """
        raw = os.environ.get(ENV_API_KEY)
        if raw is None:
            return None
        stripped = raw.strip()
        return stripped or None
