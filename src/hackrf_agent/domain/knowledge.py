"""Knowledge-corpus loader.

Pure data. Zero hardware access. Zero LLM involvement.

The corpus lives on disk under ``knowledge/`` at the repo root (or wherever
``HACKRF_KNOWLEDGE_DIR`` points). Two layers:

- ``knowledge/<topic>/*.md`` — prose files exposed by the ``knowledge_read``
  and ``knowledge_list_topics`` verbs.
- ``knowledge/records/*.json`` — typed JSON arrays exposed by the
  ``knowledge_lookup_*`` verbs.

Every function here refuses paths that escape the corpus root, refuses
symlinks, and enforces a 1 MB per-file cap on markdown reads to bound the
LLM's tool-result payload.

Corpus discovery order:

1. ``HACKRF_KNOWLEDGE_DIR`` env var (dev override).
2. An upward walk from this file looking for ``knowledge/MANIFEST.md``.
3. Repo root inferred from ``__file__`` (four levels up from the module).

The loader caches a small in-memory index (topic list + record files) for
the duration of the process. Records are read fresh on every request so
authors can edit JSON without restarting the MCP server; the topic-list
index refreshes on every call too — the corpus is small enough that a
filesystem walk is cheap.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

_MAX_MD_BYTES: int = 1_048_576  # 1 MB per markdown file
_TOPIC_NAME_RE: re.Pattern[str] = re.compile(r"^[a-z0-9][a-z0-9\-]{0,63}$")
_FILE_NAME_RE: re.Pattern[str] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-_.]{0,127}$")


class KnowledgeError(ValueError):
    """Raised when a knowledge request violates path/name constraints."""


@dataclass(frozen=True)
class KnowledgePaths:
    """On-disk layout for the corpus. Purely paths + resolvers."""

    root: Path

    @property
    def records_dir(self) -> Path:
        return self.root / "records"

    @property
    def manifest(self) -> Path:
        return self.root / "MANIFEST.md"

    def topic_dir(self, topic: str) -> Path:
        """Return the directory for *topic*, or raise if the name is unsafe.

        Denies path traversal by refusing anything that doesn't match the
        ``[a-z0-9][a-z0-9\\-]*`` pattern. Also denies symlink escapes by
        resolving and checking ``relative_to(self.root)``.
        """
        if not _TOPIC_NAME_RE.match(topic):
            raise KnowledgeError(
                f"invalid topic name {topic!r} (must match "
                f"{_TOPIC_NAME_RE.pattern!r})"
            )
        candidate = self.root / topic
        return self._ensure_inside(candidate)

    def topic_file(self, topic: str, name: str) -> Path:
        """Return the path to ``<topic>/<name>``, safety-checked."""
        if not _FILE_NAME_RE.match(name):
            raise KnowledgeError(
                f"invalid file name {name!r} (must match "
                f"{_FILE_NAME_RE.pattern!r})"
            )
        candidate = self.topic_dir(topic) / name
        return self._ensure_inside(candidate)

    def record_file(self, filename: str) -> Path:
        """Return the path to ``records/<filename>``, safety-checked."""
        if not _FILE_NAME_RE.match(filename):
            raise KnowledgeError(f"invalid record filename {filename!r}")
        candidate = self.records_dir / filename
        return self._ensure_inside(candidate)

    def _ensure_inside(self, candidate: Path) -> Path:
        """Resolve *candidate* and confirm it lives under ``self.root``."""
        try:
            resolved = candidate.resolve(strict=False)
            root_resolved = self.root.resolve(strict=False)
            resolved.relative_to(root_resolved)
        except (ValueError, OSError) as e:
            raise KnowledgeError(
                f"path {candidate} escapes knowledge root {self.root}"
            ) from e
        return resolved


# ---------------------------------------------------------------------------
# Corpus discovery
# ---------------------------------------------------------------------------


def _discover_root() -> Path:
    """Locate the corpus on disk.

    Checks ``HACKRF_KNOWLEDGE_DIR`` first, then walks up from this module
    looking for a ``knowledge/MANIFEST.md`` sibling.
    """
    env = os.environ.get("HACKRF_KNOWLEDGE_DIR")
    if env:
        return Path(env).expanduser()
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "knowledge" / "MANIFEST.md"
        if candidate.is_file():
            return candidate.parent
    # Last-resort default — repo root as inferred from src/hackrf_agent/domain
    # is here.parent.parent.parent.parent — but we don't want to fail silently.
    raise KnowledgeError(
        "cannot locate knowledge/ corpus; set HACKRF_KNOWLEDGE_DIR "
        "or run from a checkout containing knowledge/MANIFEST.md"
    )


@lru_cache(maxsize=1)
def _default_paths_cached() -> KnowledgePaths:
    """Cached wrapper around _discover_root — invalidated by ``clear_cache``."""
    return KnowledgePaths(root=_discover_root())


def default_paths() -> KnowledgePaths:
    """Return the process-wide default ``KnowledgePaths``.

    Tests can override by setting ``HACKRF_KNOWLEDGE_DIR`` and calling
    ``clear_cache()``.
    """
    return _default_paths_cached()


def clear_cache() -> None:
    """Invalidate the cached ``KnowledgePaths`` (used by tests)."""
    _default_paths_cached.cache_clear()


# ---------------------------------------------------------------------------
# Prose-file operations
# ---------------------------------------------------------------------------


def list_topics(paths: KnowledgePaths) -> list[dict[str, Any]]:
    """Return every topic dir and its markdown files.

    Each returned item is ``{"topic": str, "files": list[str]}``. Files are
    sorted; topics are sorted. The ``records/`` subdir is excluded — records
    are exposed by ``knowledge_lookup_*`` verbs, not by ``knowledge_read``.
    Hidden files/dirs (starting with ``.``) are skipped.
    """
    if not paths.root.is_dir():
        raise KnowledgeError(f"knowledge root does not exist: {paths.root}")

    topics: list[dict[str, Any]] = []
    for entry in sorted(paths.root.iterdir()):
        if not entry.is_dir():
            continue
        name = entry.name
        if name.startswith(".") or name == "records":
            continue
        # Enforce naming even during discovery — a stray path here would
        # otherwise be un-reachable via knowledge_read.
        if not _TOPIC_NAME_RE.match(name):
            continue
        md_files = sorted(
            f.name
            for f in entry.iterdir()
            if f.is_file()
            and f.suffix == ".md"
            and _FILE_NAME_RE.match(f.name)
        )
        topics.append({"topic": name, "files": md_files})
    return topics


def read_file(paths: KnowledgePaths, topic: str, name: str) -> dict[str, Any]:
    """Return the contents of ``<topic>/<name>``.

    Enforces:
    - Both ``topic`` and ``name`` match the safe-name regexes.
    - Resolved path is inside ``paths.root`` (no symlink escapes).
    - Extension is ``.md`` (records are read via ``knowledge_lookup_*``).
    - File size <= 1 MB.
    """
    if not name.endswith(".md"):
        raise KnowledgeError(f"only .md files are readable via this verb ({name!r})")
    resolved = paths.topic_file(topic, name)
    if not resolved.is_file():
        raise KnowledgeError(f"no such file: {topic}/{name}")
    size = resolved.stat().st_size
    if size > _MAX_MD_BYTES:
        raise KnowledgeError(
            f"file too large ({size} bytes > {_MAX_MD_BYTES} cap): {topic}/{name}"
        )
    text = resolved.read_text(encoding="utf-8")
    return {"topic": topic, "name": name, "bytes": size, "content": text}


def search(
    paths: KnowledgePaths,
    query: str,
    max_results: int = 20,
) -> list[dict[str, Any]]:
    """Case-insensitive substring search across every markdown file.

    Returns a list of ``{"topic", "name", "line", "text"}`` hits, sorted by
    (topic, name, line). Caps at ``max_results`` — the caller usually
    surfaces the count of dropped hits separately.
    """
    if not query.strip():
        raise KnowledgeError("query must be non-empty")
    needle = query.casefold()
    hits: list[dict[str, Any]] = []
    for entry in list_topics(paths):
        topic = entry["topic"]
        for name in entry["files"]:
            file_path = paths.topic_file(topic, name)
            try:
                content = file_path.read_text(encoding="utf-8")
            except OSError:
                continue
            for i, line in enumerate(content.splitlines(), start=1):
                if needle in line.casefold():
                    hits.append(
                        {
                            "topic": topic,
                            "name": name,
                            "line": i,
                            "text": line.strip()[:200],
                        }
                    )
                    if len(hits) >= max_results:
                        return hits
    return hits


# ---------------------------------------------------------------------------
# Record-file operations
# ---------------------------------------------------------------------------


def load_records(paths: KnowledgePaths, filename: str) -> list[dict[str, Any]]:
    """Load a records/*.json file and return its list of records.

    Raises ``KnowledgeError`` on parse errors or if the top-level JSON isn't
    an array.
    """
    resolved = paths.record_file(filename)
    if not resolved.is_file():
        raise KnowledgeError(f"no such record file: {filename}")
    try:
        data = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise KnowledgeError(f"invalid JSON in {filename}: {e}") from e
    if not isinstance(data, list):
        raise KnowledgeError(f"records file {filename} must be a JSON array")
    return data


def lookup_band(
    paths: KnowledgePaths, freq_hz: int
) -> list[dict[str, Any]]:
    """Return every ``bands.json`` record whose start_hz..stop_hz covers
    *freq_hz*.

    Overlapping bands (e.g. amateur 70 cm overlaps EU ISM 433) can produce
    multiple hits. Callers sort by whichever heuristic they prefer.
    """
    records = load_records(paths, "bands.json")
    hits: list[dict[str, Any]] = []
    for rec in records:
        body = rec.get("technical_body", {})
        start = body.get("start_hz")
        stop = body.get("stop_hz")
        if not isinstance(start, int) or not isinstance(stop, int):
            continue
        if start <= freq_hz <= stop:
            hits.append(rec)
    return hits


def lookup_modulation(
    paths: KnowledgePaths, name_or_alias: str
) -> dict[str, Any] | None:
    """Return the first ``modulations.json`` record whose name/alias
    case-insensitively matches *name_or_alias*, or ``None`` if no hit.
    """
    if not name_or_alias.strip():
        raise KnowledgeError("name must be non-empty")
    needle = name_or_alias.strip().casefold()
    for rec in load_records(paths, "modulations.json"):
        candidates: list[str] = []
        rec_name = rec.get("name")
        if isinstance(rec_name, str):
            candidates.append(rec_name)
        rec_id = rec.get("id")
        if isinstance(rec_id, str):
            candidates.append(rec_id)
        for alias in rec.get("aliases", []):
            if isinstance(alias, str):
                candidates.append(alias)
        if any(c.casefold() == needle for c in candidates):
            return rec
    return None


# ---------------------------------------------------------------------------
# Claim-verification trap catalog
# ---------------------------------------------------------------------------

#
# Seeded from plan-knowledge.md "Explicitly disputed / ambiguous entries"
# and the funnel-invariant claims in plan-organization.md. Each entry:
#
#   patterns: substrings (case-insensitive) that must ALL appear in the
#             normalized claim for the trap to fire.
#   verdict:  "true" | "false" | "needs_qualification"
#   note:     one-line explanation returned with the verdict.
#   citations: bibliography IDs backing the verdict.
#
_TRAP_CATALOG: list[dict[str, Any]] = [
    {
        "patterns": ["ook", "ask", "same"],
        "verdict": "needs_qualification",
        "note": (
            "OOK is a special case of ASK with 2 levels and 100% modulation "
            "depth. Many decoders and specs treat them as distinct."
        ),
        "citations": ["proakis-digital-comm"],
    },
    {
        "patterns": ["fsk", "gfsk", "same"],
        "verdict": "false",
        "note": (
            "GFSK is FSK with a Gaussian pulse-shaping filter. The BT product "
            "matters for adjacent-channel rejection and for distinguishing "
            "protocols (Bluetooth BT~0.5 vs GSM BT~0.3)."
        ),
        "citations": ["proakis-digital-comm"],
    },
    {
        "patterns": ["hackrf", "tx", "ads-b"],
        "verdict": "false",
        "note": (
            "1090 MHz is BLOCKED for TX in the RiskAssessor — transmitting "
            "ADS-B is prohibited to protect aviation safety-of-life."
        ),
        "citations": ["fcc-part-87", "hackrf-agent-repo"],
    },
    {
        "patterns": ["hackrf", "tx", "1090"],
        "verdict": "false",
        "note": (
            "1090 MHz is BLOCKED for TX in the RiskAssessor — transmitting "
            "on the ADS-B/SSR/TCAS band is prohibited."
        ),
        "citations": ["fcc-part-87", "hackrf-agent-repo"],
    },
    {
        "patterns": ["hackrf", "gps", "spoof"],
        "verdict": "false",
        "note": (
            "GPS L1/L2/L5 are BLOCKED for TX; GPS spoofing is a federal "
            "offense in the US."
        ),
        "citations": ["itu-rr", "hackrf-agent-repo"],
    },
    {
        "patterns": ["hackrf", "full-duplex"],
        "verdict": "false",
        "note": (
            "The HackRF One is half-duplex — the T/R switch is a physical "
            "SPDT and RX/TX cannot run simultaneously."
        ),
        "citations": ["hackrf-docs"],
    },
    {
        "patterns": ["hackrf", "12-bit"],
        "verdict": "false",
        "note": (
            "The HackRF's MAX5864 ADC/DAC is 8-bit interleaved I/Q. Practical "
            "SFDR is ~48 dB."
        ),
        "citations": ["hackrf-docs"],
    },
    {
        "patterns": ["hackrf", "8-bit"],
        "verdict": "true",
        "note": "The HackRF's ADC/DAC is indeed 8-bit interleaved I/Q.",
        "citations": ["hackrf-docs"],
    },
    {
        "patterns": ["dc spike", "signal"],
        "verdict": "false",
        "note": (
            "The DC spike is LO leakage + amplifier DC offset, not a signal. "
            "Use target_freq_hz to offset it away from your target."
        ),
        "citations": ["hackrf-agent-repo"],
    },
    {
        "patterns": ["target_freq_hz", "center_freq_hz", "same"],
        "verdict": "false",
        "note": (
            "target_freq_hz offsets the tuner by ~sample_rate/4 so the DC "
            "spike lands off your target; center_freq_hz is raw tuner "
            "control."
        ),
        "citations": ["hackrf-agent-repo"],
    },
    {
        "patterns": ["airband", "tx"],
        "verdict": "false",
        "note": (
            "Aviation voice 118-137 MHz is BLOCKED for TX in the "
            "RiskAssessor (47 CFR §87.171)."
        ),
        "citations": ["fcc-part-87", "hackrf-agent-repo"],
    },
    {
        "patterns": ["cellular downlink", "tx"],
        "verdict": "false",
        "note": (
            "US cellular downlink bands are BLOCKED for TX in the "
            "RiskAssessor (Parts 22/24/27)."
        ),
        "citations": ["fcc-part-27", "hackrf-agent-repo"],
    },
    {
        "patterns": ["nyquist", "2x", "bandwidth"],
        "verdict": "true",
        "note": (
            "A real-valued signal band-limited to B Hz needs fs >= 2B; "
            "for complex baseband (IQ), fs covers +/- fs/2 around DC."
        ),
        "citations": ["proakis-digital-comm"],
    },
    {
        "patterns": ["manchester", "keyfob"],
        "verdict": "needs_qualification",
        "note": (
            "Many keyfobs (315/433 MHz OOK) use Manchester encoding at 1-4 "
            "kbps, but not all — some vendors use PWM or NRZ."
        ),
        "citations": ["rtl-433-github"],
    },
]


def verify_claim(text: str) -> dict[str, Any]:
    """Grade a factual claim about the corpus/HackRF against the trap catalog.

    Returns ``{"verdict": <str>, "note": <str>, "citations": [<str>, ...]}``.

    ``verdict`` is one of:
    - ``"true"`` — trap catalog confirms the claim.
    - ``"false"`` — trap catalog contradicts the claim.
    - ``"needs_qualification"`` — claim is partially right or context-dependent.
    - ``"unverified"`` — no trap fired; the corpus does not confirm or deny.

    The trap catalog only fires on substring-match; the LLM is instructed
    (via the prompt) to caveat ``unverified`` results.
    """
    if not text.strip():
        raise KnowledgeError("claim must be non-empty")
    normalized = text.casefold()
    for trap in _TRAP_CATALOG:
        patterns = trap["patterns"]
        if all(p.casefold() in normalized for p in patterns):
            return {
                "verdict": trap["verdict"],
                "note": trap["note"],
                "citations": list(trap["citations"]),
                "matched_patterns": list(patterns),
            }
    return {
        "verdict": "unverified",
        "note": (
            "No entry in the trap catalog matched this claim. The corpus "
            "does not confirm or deny it — caveat accordingly."
        ),
        "citations": [],
        "matched_patterns": [],
    }
