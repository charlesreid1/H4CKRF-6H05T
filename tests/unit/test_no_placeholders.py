"""Regression guard against drift-cleanup regressions.

Greps the whole source tree for phrases that mark unfinished work or
historical build-plan references. Every hit is a bug: either the code
is genuinely unfinished (fix it) or the language is stale drift (drop
it). Fixture directories and the attic/ archive are exempt by explicit
path.

If this test starts failing, run:

    grep -rn 'placeholder' --include='*.md' --include='*.py' src/ docs/ knowledge/

and either implement the missing verb or delete the stale prose.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent

# Roots we grep — the shipped surface. attic/, .venv/, tests/fixtures/iq/,
# __pycache__, egg-info are exempt.
SEARCH_ROOTS: tuple[Path, ...] = (
    REPO_ROOT / "src",
    REPO_ROOT / "docs",
    REPO_ROOT / "knowledge",
    REPO_ROOT / "scripts",
    REPO_ROOT / "skills",
    REPO_ROOT / "tests",
    REPO_ROOT / "Readme.md",
    REPO_ROOT / "CHANGELOG.md",
)

# Phrases that must not appear anywhere in the shipped surface. Case-
# insensitive substring match. Adding a phrase here is a promise never to
# ship it again.
FORBIDDEN_PHRASES: tuple[str, ...] = (
    "placeholder",
    "TODO",
    "FIXME",
    "XXX",
    "not yet implemented",
    "until Part ",
    "[planned]",
    "Skeleton — Tier",
    "plan-organization",
    "plan-knowledge",
    "plan-bender",
)

# Path segments that are exempt from the grep entirely.
_EXEMPT_PATH_SEGMENTS: tuple[str, ...] = (
    "attic/",
    "__pycache__/",
    ".egg-info/",
    ".venv/",
    "tests/fixtures/iq/",
    # This file itself contains the forbidden phrases as string literals.
    "test_no_placeholders.py",
    # The regenerator test also references decode_ook stub as a phrase.
    "test_schema_regenerator.py",
)

def _pattern_for(phrase: str) -> str:
    esc = re.escape(phrase)
    # Bare-word markers (TODO / FIXME / XXX / placeholder) need word
    # boundaries so 'xxxx' or 'stubbed' don't false-positive. Multi-word
    # phrases already have enough anchoring in their body.
    if phrase.isalnum() and phrase.isupper():
        return rf"\b{esc}\b"
    if phrase.isalnum():
        return rf"\b{esc}\b"
    return esc


_FORBIDDEN_RE = re.compile(
    "|".join(_pattern_for(p) for p in FORBIDDEN_PHRASES),
    re.IGNORECASE,
)


def _is_exempt(path: Path) -> bool:
    text = str(path)
    return any(seg in text for seg in _EXEMPT_PATH_SEGMENTS)


def _iter_files() -> list[Path]:
    files: list[Path] = []
    for root in SEARCH_ROOTS:
        if root.is_file():
            files.append(root)
            continue
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if _is_exempt(path):
                continue
            if path.suffix not in (".md", ".py", ".json", ".sql", ".toml"):
                continue
            files.append(path)
    return files


def test_no_forbidden_phrases_in_shipped_surface() -> None:
    """Every forbidden phrase found is a drift-cleanup regression."""
    offenders: list[tuple[str, int, str, str]] = []
    for path in _iter_files():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            m = _FORBIDDEN_RE.search(line)
            if m:
                offenders.append((str(path.relative_to(REPO_ROOT)), lineno, m.group(0), line.strip()))
    if offenders:
        lines = [
            f"{p}:{ln}: matched {phrase!r} — {text}"
            for p, ln, phrase, text in offenders[:30]
        ]
        raise AssertionError(
            "Forbidden phrase(s) reintroduced into the shipped surface:\n"
            + "\n".join(lines)
        )
