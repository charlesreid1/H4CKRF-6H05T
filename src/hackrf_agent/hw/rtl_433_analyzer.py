"""``rtl_433`` adapter — analyze IQ captures for pulse timing and protocol matches.

``rtl_433`` is a battle-tested SDR decoder that knows ~200 device protocols.
This adapter shells out to ``rtl_433 -A`` (analyse mode) and returns structured
results: pulse-width stats, modulation guess, and any protocol matches.

Usage::

    from hackrf_agent.hw.rtl_433_analyzer import analyze

    result = await analyze(iq_path=Path("capture.iq"), sample_rate_hz=2_000_000)
    # result["protocol_matches"]  → list of decoded device dicts
    # result["pulse_stats"]       → {min_us, max_us, median_us} or None
    # result["modulation_guess"]  → "PPM" / "PWM" / "Manchester" / …
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
from pathlib import Path
from typing import Any

from hackrf_agent.hw.exceptions import Rtl433Failed, Rtl433NotInstalled

# ---------------------------------------------------------------------------
# Regexes for the rtl_433 -A stderr output
# ---------------------------------------------------------------------------

_PULSE_RE = re.compile(
    r"pulse_width.*?min\s+(\d+).*?max\s+(\d+).*?median\s+(\d+)", re.S
)
_MOD_RE = re.compile(r"Guessing modulation:\s+(.+)")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def analyze(
    iq_path: Path,
    sample_rate_hz: int,
    timeout_s: float = 30.0,
) -> dict[str, Any]:
    """Run ``rtl_433 -A`` on *iq_path* and return structured results.

    Args:
        iq_path: Path to a ``cs8`` (signed int8 interleaved) IQ file.
        sample_rate_hz: Sample rate of the file. Must match ``capture_iq``.
        timeout_s: Maximum wall-clock seconds for the subprocess.

    Returns:
        A dict with keys ``protocol_matches``, ``pulse_stats``,
        ``modulation_guess``, and ``rtl_433_stderr`` (for debugging).

    Raises:
        Rtl433NotInstalled: ``rtl_433`` is not on PATH.
        Rtl433Failed: Subprocess timed out or exited with an unexpected code.
    """
    exe = shutil.which("rtl_433")
    if exe is None:
        raise Rtl433NotInstalled(
            "rtl_433 not found on PATH. Install: `brew install rtl_433` "
            "or see https://github.com/merbanan/rtl_433"
        )

    argv = [
        exe,
        "-r", str(iq_path),
        "-s", str(sample_rate_hz),
        "-f", "cs8",
        "-A",
        "-F", "json",
        "-M", "level",
    ]

    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout_s)
    except asyncio.TimeoutError:
        proc.kill()
        raise Rtl433Failed(f"rtl_433 timed out after {timeout_s}s") from None

    # Return code 1 = "ran cleanly but no protocol matched" — still OK.
    if proc.returncode not in (0, 1):
        raise Rtl433Failed(err.decode(errors="replace")[:2000])

    matches: list[dict[str, Any]] = [
        json.loads(line) for line in out.splitlines() if line.strip()
    ]

    err_text = err.decode(errors="replace")
    pulse_match = _PULSE_RE.search(err_text)
    mod_match = _MOD_RE.search(err_text)

    pulse_stats: dict[str, int] | None = None
    if pulse_match:
        pulse_stats = {
            "min_us": int(pulse_match[1]),
            "max_us": int(pulse_match[2]),
            "median_us": int(pulse_match[3]),
        }

    return {
        "protocol_matches": matches,
        "pulse_stats": pulse_stats,
        "modulation_guess": mod_match[1].strip() if mod_match else "unknown",
        "rtl_433_stderr": err_text,
    }
