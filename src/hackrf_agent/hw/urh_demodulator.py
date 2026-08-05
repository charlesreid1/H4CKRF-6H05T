"""``urh_cli`` adapter — parameterised IQ demodulation to raw bitstream.

URH (Universal Radio Hacker) is a general-purpose SDR demodulator. Unlike
``rtl_433``, which matches against a database of known device protocols, URH
is told *how* to demodulate (modulation type, samples-per-symbol, threshold,
etc.) and returns the raw bits. The caller (or a follow-up inference step)
recognises framing, CRC, sync words.

Usage::

    from hackrf_agent.hw.urh_demodulator import demodulate

    bits = await demodulate(
        iq_path=Path("capture.iq"),
        sample_rate_hz=2_000_000,
        modulation="ASK",
        samples_per_symbol=1000,
    )
    # bits["bits"]       → "1010110001..."
    # bits["bit_count"]  → 128
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from hackrf_agent.hw.exceptions import UrhFailed, UrhNotInstalled

# ---------------------------------------------------------------------------
# IQ format conversion (cs8 → complex float32)
# ---------------------------------------------------------------------------


def _cs8_to_complex_bytes(raw: bytes) -> bytes:
    """Convert signed-int8 interleaved IQ to float32 interleaved IQ.

    ``capture_iq`` writes libhackrf's native ``cs8`` format: one int8 for I,
    one int8 for Q, repeating.  URH's CLI eats ``.complex``: float32
    interleaved in the same order (I0, Q0, I1, Q1, …).

    Returns the raw bytes of the float32 array (``.tobytes()``), ready to
    write into a temp file.
    """
    arr = np.frombuffer(raw, dtype=np.int8).astype(np.float32)
    arr *= np.float32(1.0 / 128.0)  # normalise to roughly [-1, +1]
    return arr.tobytes()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def demodulate(
    iq_path: Path,
    sample_rate_hz: int,
    modulation: str,
    samples_per_symbol: int,
    *,
    threshold: float | None = None,
    invert: bool = False,
    bit_order: str | None = None,
    timeout_s: float = 30.0,
) -> dict[str, Any]:
    """Run ``urh_cli`` on *iq_path* and return the demodulated bitstream.

    Args:
        iq_path: Path to a ``cs8`` IQ file (converted to ``.complex`` on the
            fly — the original file is never modified).
        sample_rate_hz: Sample rate of the file.
        modulation: ``"ASK"``, ``"FSK"``, ``"GFSK"``, or ``"PSK"``.
        samples_per_symbol: Samples per symbol (sample_rate / symbol_rate).
        threshold: Optional amplitude threshold (0.0–1.0).
        invert: If True, invert output bits.
        bit_order: ``"lsb"`` or ``"msb"`` (optional).
        timeout_s: Maximum wall-clock seconds for the subprocess.

    Returns:
        A dict with keys ``bits``, ``bit_count``, ``urh_stderr`` (for
        debugging), and ``params`` (the effective parameters used).

    Raises:
        UrhNotInstalled: ``urh_cli`` is not on PATH.
        UrhFailed: Subprocess timed out or exited with an unexpected code.
    """
    exe = shutil.which("urh_cli")
    if exe is None:
        raise UrhNotInstalled(
            "urh_cli not found on PATH. Install: `pipx install urh` "
            "or see https://github.com/jopohl/urh"
        )

    # -- convert cs8 → complex float32, write temp file -----------------------
    raw_cs8 = iq_path.read_bytes()
    complex_bytes = _cs8_to_complex_bytes(raw_cs8)

    # Write into the *parent* directory of iq_path so the temp file is still
    # inside the session root (satisfies the session_paths contract).
    tmp_fd, tmp_path_str = tempfile.mkstemp(
        suffix=".complex",
        prefix="urh_",
        dir=iq_path.parent,
    )
    tmp_path = Path(tmp_path_str)
    try:
        tmp_path.write_bytes(complex_bytes)

        # -- build argv -------------------------------------------------------
        argv = [
            exe,
            "-f", str(tmp_path),
            "-s", str(sample_rate_hz),
            "-m", modulation.lower(),
            "-sps", str(samples_per_symbol),
        ]
        if threshold is not None:
            argv.extend(["-thresh", str(threshold)])
        if invert:
            argv.append("-invert")
        if bit_order is not None:
            argv.extend(["-bo", bit_order.lower()])

        # -- run --------------------------------------------------------------
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout_s)
        except asyncio.TimeoutError:
            proc.kill()
            raise UrhFailed(f"urh_cli timed out after {timeout_s}s") from None

        if proc.returncode != 0:
            raise UrhFailed(err.decode(errors="replace")[:2000])

        bits_raw = out.decode(errors="replace").strip()
        # urh_cli may wrap output — take the first whitespace-free token that
        # looks like a bitstring.
        bits = bits_raw
        for token in bits_raw.split():
            if all(c in "01" for c in token) and len(token) > 8:
                bits = token
                break

        return {
            "bits": bits,
            "bit_count": sum(1 for c in bits if c in "01"),
            "urh_stderr": err.decode(errors="replace"),
            "params": {
                "modulation": modulation,
                "samples_per_symbol": samples_per_symbol,
                "threshold": threshold,
                "invert": invert,
                "bit_order": bit_order,
            },
        }

    finally:
        # Always clean up the temp .complex file.
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass
