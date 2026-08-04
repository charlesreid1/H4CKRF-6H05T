"""Escape-hatch subprocess wrapper for hackrf_* CLI tools.

Small, dumb, allowlisted. The executor (Part 5) builds the argv from
typed args — the LLM never synthesises argv text. This module only
validates and runs what it's given.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from hackrf_agent.hw.exceptions import (
    HackrfError,
    HackrfTimeoutError,
    InvalidHackrfArgError,
)

# ---------------------------------------------------------------------------
# The full set of executables we ever invoke. Any argv[0] outside this set
# is refused before Popen. LLM-supplied strings do NOT reach argv[0] — the
# executor picks the tool by name, the driver builds the argv.
# ---------------------------------------------------------------------------

_ALLOWED_TOOLS: frozenset[str] = frozenset(
    {
        "hackrf_info",
        "hackrf_sweep",
        "hackrf_transfer",
        "hackrf_spiflash",
    }
)

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SubprocessResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    duration_s: float


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_argv(argv: tuple[str, ...]) -> None:
    """Reject any argv that looks unsafe, *before* ``Popen``.

    The executor should never pass bad argv, but belt-and-braces: we
    reject shell metacharacters, null bytes, and tools outside the
    allowlist regardless of who the caller is.
    """
    if not argv:
        raise InvalidHackrfArgError("argv is empty")
    if not all(isinstance(a, str) for a in argv):
        raise InvalidHackrfArgError("argv contains non-string element")
    tool = argv[0]
    if tool not in _ALLOWED_TOOLS:
        raise InvalidHackrfArgError(f"tool {tool!r} not in allowlist {sorted(_ALLOWED_TOOLS)}")
    # Reject control characters that could interact badly with terminal
    # emulation or tool-specific parsers, even without shell=True.
    for a in argv[1:]:
        if any(c in a for c in ("\n", "\r", "\x00")):
            raise InvalidHackrfArgError(f"control character in argv: {a!r}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def run_hackrf_tool(
    argv: Sequence[str],
    *,
    timeout_s: int = 60,
    cwd: Path | None = None,
) -> SubprocessResult:
    """Run a hackrf_* CLI tool with the given argv and return its result.

    Args:
        argv: full argv INCLUDING the executable name at [0]. The executor
              is responsible for building this — never let LLM text land
              here unvalidated.
        timeout_s: seconds before we SIGTERM the child.
        cwd: working directory; default is the caller's cwd.

    Raises:
        InvalidHackrfArgError: argv[0] is not in ``_ALLOWED_TOOLS``, or
            argv is empty, or any element is not a str, or control
            characters are present.
        HackrfTimeoutError: child did not exit within timeout.
        HackrfError: child exited with non-zero returncode (wraps stderr).
    """
    argv = tuple(argv)
    _validate_argv(argv)

    loop = asyncio.get_running_loop()
    start = loop.time()

    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd) if cwd else None,
        )
    except FileNotFoundError as e:
        raise InvalidHackrfArgError(
            f"executable {argv[0]!r} not found on PATH — is libhackrf installed?"
        ) from e

    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except TimeoutError as e:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=2)
        except TimeoutError:
            proc.kill()
            await proc.wait()
        raise HackrfTimeoutError(f"{argv[0]!r} did not exit within {timeout_s}s") from e

    duration = loop.time() - start

    result = SubprocessResult(
        argv=argv,
        returncode=proc.returncode or 0,
        stdout=stdout_b.decode("utf-8", errors="replace"),
        stderr=stderr_b.decode("utf-8", errors="replace"),
        duration_s=duration,
    )

    if result.returncode != 0:
        raise HackrfError(
            f"{argv[0]} exited with code {result.returncode}: {result.stderr.strip()[:400]}"
        )

    return result
