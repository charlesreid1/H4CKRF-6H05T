# IQ Handling

Everything about `.iq` files: how big they get, what format they're
in, where they live, how to move them between H4CKRF and external
tools like GQRX, URH, and Inspectrum.

If you just want a decoded flag, [ctf_recipes.md](ctf_recipes.md) is
the file you want. This one is for when the recipe doesn't work and
you need to open the file in something else — or when the puzzle
hands you an IQ file from an unknown source.

---

## The format H4CKRF uses

`hackrf-agent` writes and reads exactly one format: **`.cs8`** —
signed 8-bit interleaved I/Q, little-endian, no header.

| Property | Value |
|---|---|
| Extension | `.cs8` (canonical) or `.iq` (aliased in tool arguments) |
| Sample type | `int8` |
| Layout | `I0 Q0 I1 Q1 …` (I first, always) |
| Endianness | Little-endian |
| Header | None |
| Bytes per sample | 2 |
| Value range | `[-128, +127]` |

This matches what `hackrf_transfer` writes and reads natively. Every
`capture_iq` output and every `iq_path` argument to a decoder assumes
this format.

Files above **1 GiB (1,073,741,824 bytes)** are rejected by the
loader (see `MAX_IQ_FILE_BYTES` in `src/hackrf_agent/hw/analysis.py`).
Decimate at capture time or split the file if you need to work with
something bigger.

---

## Size and time math

Interleaved 2-byte samples:

```
bytes = sample_rate_hz × duration_s × 2
```

Quick reference:

| Sample rate | 1 s | 10 s | 60 s |
|---|---|---|---|
| 2 Msps | 4 MB | 40 MB | 240 MB |
| 4 Msps | 8 MB | 80 MB | 480 MB |
| 8 Msps | 16 MB | 160 MB | 960 MB |
| 20 Msps | 40 MB | 400 MB | 2.4 GB (over cap!) |

The 1 GiB cap kicks in around **12.5 s at 20 Msps** or **60 s at 8
Msps**. Plan captures accordingly.

Going the other way — given a file of unknown provenance:

```
samples = size_bytes / 2      # for .cs8 or .cu8
duration = samples / fs       # if you know fs
```

If someone hands you a file and doesn't tell you the sample rate,
guess 2 Msps first. If the spectrogram looks squished on the time
axis, try 8 Msps.

---

## Where files live

Every session gets its own directory under
`~/.hackrf-agent/sessions/`. The layout:

```
~/.hackrf-agent/sessions/
└── 2026-08-07T15-30-11_ab12cd/          # session_id
    ├── iq/
    │   ├── capture-1723041011000-abc123.iq
    │   └── capture-1723041020000-def456.iq
    ├── summaries/
    │   └── sweep-*.json
    └── logs/
```

Filenames follow `{prefix}-{unix_ms}-{uuid6}.iq` — clash-safe, sorts
chronologically. The path is minted by the executor, not the LLM —
you can never pass an `iq_path` argument that points outside the
session root; the path-safety check rejects `..` traversal.

**When does a session end?** When the CLI or MCP server process
exits. Files persist forever until you delete them. For the MCP
server, one host session typically corresponds to one server
process, so IQ paths stay stable for the whole conversation.

### Cleaning up

There is no automatic cleanup. Two failure modes:

- **You'll fill the disk.** A day of DEF CON captures at 8 Msps can
  easily hit 20 GB. Sweep `~/.hackrf-agent/sessions/` between
  puzzles.
- **You'll lose the file you wanted.** If you delete an old session
  dir, the `iq_path` recorded in the audit log is now dangling.
  Query the audit log with `hackrf-agent audit tail --trace <uuid>`
  to reconstruct the file's original name before you nuke.

Rough cleanup:

```bash
# Delete sessions older than 7 days
find ~/.hackrf-agent/sessions/ -mindepth 1 -maxdepth 1 -type d \
  -mtime +7 -exec rm -rf {} +
```

---

## Format cross-reference

You'll encounter other formats in the wild. Table lifted from
[../knowledge/iq-formats/reference.md](../knowledge/iq-formats/reference.md):

| Extension | Sample type | Bytes/sample | Source |
|---|---|---|---|
| `.cs8` | int8, signed | 2 | HackRF (native) |
| `.cu8` | uint8, offset 127 | 2 | RTL-SDR (`rtl_sdr`) |
| `.cs16` | int16, signed | 4 | LimeSDR, USRP |
| `.cf32` | float32 | 8 | GNU Radio default |
| `.cf64` | float64 | 16 | rare — Matlab exports |
| `.wav` (float32) | float32 stereo | 8 | SDR#, HDSDR |
| `.wav` (int16) | int16 stereo | 4 | SDR# lower precision |
| `.sigmf-data` + `.sigmf-meta` | any (declared in meta) | varies | Community standard |

Every format above is little-endian; every one has I first. Big-endian
variants exist but are rare — symptom is a mirror-imaged spectrum.

**`.iq` alone is ambiguous.** Never trust the extension without
knowing the tool that wrote it. When a CTF hands you an `.iq` file,
assume `.cs8` first, `.cu8` second, `.cf32` third — those are the
overwhelming majority.

---

## Converting to `.cs8`

To use an external capture with H4CKRF's decoders, convert it first.
The command-line one-liners below assume you have `numpy` and a Python
REPL — the file layer is just `numpy.fromfile` + `astype`.

### `.cu8` (RTL-SDR) → `.cs8`

```python
import numpy as np
u = np.fromfile('capture.cu8', dtype=np.uint8)
s = (u.astype(np.int16) - 127).astype(np.int8)
s.tofile('capture.cs8')
```

The `-127` shift converts offset-binary uint8 to signed int8. **Skip
this and you'll get a huge fake DC spike.**

### `.cs16` (LimeSDR) → `.cs8`

```python
import numpy as np
s16 = np.fromfile('capture.cs16', dtype=np.int16)
s8 = (s16 // 256).astype(np.int8)     # keep the top byte
s8.tofile('capture.cs8')
```

You lose 8 bits of dynamic range. If the source signal was low-amplitude
this may quantize to noise; scale first if you can.

### `.cf32` (GNU Radio) → `.cs8`

```python
import numpy as np
f = np.fromfile('capture.cf32', dtype=np.float32)
# GNU Radio floats are typically in [-1, 1]; scale to int8
s8 = np.clip(f * 127, -128, 127).astype(np.int8)
s8.tofile('capture.cs8')
```

If your `.cf32` isn't in `[-1, 1]` you'll clip. Check the range first:
`f.min()`, `f.max()`.

### `.wav` → `.cs8`

```python
import numpy as np
from scipy.io import wavfile
fs, data = wavfile.read('capture.wav')  # stereo: shape (N, 2)
# WAV I/Q by convention: channel 0 = I, channel 1 = Q
iq = data.astype(np.float32).flatten()   # interleave I,Q,I,Q
s8 = np.clip(iq / max(abs(iq.min()), abs(iq.max())) * 127, -128, 127)
s8.astype(np.int8).tofile('capture.cs8')
```

Confirm channel order — some tools (rare) write Q,I. If your
spectrum looks mirrored, swap them.

### SigMF pairs

If you have `.sigmf-data` + `.sigmf-meta`, read `core:datatype`
from the metadata:

- `cf32_le` → treat as `.cf32`
- `ci16_le` → treat as `.cs16`
- `cu8` → treat as `.cu8`
- `ci8_le` → **already `.cs8`**, just rename

Also grab `core:sample_rate` and pass it to every decoder call.

---

## Handoff to external viewers

You'll want a real spectrogram sooner or later. `analyze_iq_spectrogram`
returns per-slice summary data, not an image — for a visual, use one
of these:

### Inspectrum

Best-in-class for burst analysis and manual symbol slicing.

```bash
inspectrum -r 2000000 ~/.hackrf-agent/sessions/*/iq/capture-*.iq
```

The `-r` flag is the sample rate. Inspectrum accepts `.cs8` natively.
Full walkthrough: [../knowledge/inspectrum/walkthrough.md](../knowledge/inspectrum/walkthrough.md).

### URH (Universal Radio Hacker)

Best for OOK/FSK signal reverse-engineering with an interactive
decoder builder.

- URH accepts `.cs8` (call it `int8`), `.cu8` (`uint8`), `.cs16`,
  and `.cf32`.
- Import: **File → Open File → .iq/.cs8**, set the sample rate and
  center frequency manually.
- URH's built-in Manchester / PWM decoders overlap with H4CKRF's,
  but URH is better at bit-fiddling with custom encodings.

### GQRX / CubicSDR / SDR++

Live receivers with waterfalls. They *record* to `.cs8` (GQRX default)
or `.raw`. They don't typically *play back* — they're capture tools.
Use them for real-time monitoring; use Inspectrum/URH for analysis.

See [../knowledge/gqrx-cubicsdr-sdrpp/reference.md](../knowledge/gqrx-cubicsdr-sdrpp/reference.md)
for the tool-by-tool config details.

### Baudline (Linux/macOS, legacy but great)

Old-school spectrogram viewer with excellent visual clarity. Accepts
raw interleaved samples with a manual format specification.

---

## Handoff *from* external captures

The reverse direction — someone captured with GQRX, you want to run
H4CKRF decoders on it. The `read_iq_summary` tool accepts any
`.cs8` path (including one you dropped into `~/.hackrf-agent/sessions/<id>/iq/`
manually).

**Path-safety rule.** The executor rejects `iq_path` arguments that
resolve outside the current session root. To use an external file:

1. Copy or symlink it under
   `~/.hackrf-agent/sessions/<current_session_id>/iq/`.
2. Reference the file with an `iq_path` inside that dir.

The current session ID is available via the `hackrf://sessions/current`
MCP resource, or in the response to any tool call.

If you're driving via the chat CLI, dropping files into the session
dir mid-session works — the executor's path check is per-call, not
cached.

---

## SigMF for CTF captures

If your CTF ships an IQ file, insist on a SigMF sidecar. Without one
you're guessing the sample rate and center frequency. A minimum
`.sigmf-meta` looks like:

```json
{
  "global": {
    "core:datatype": "ci8_le",
    "core:sample_rate": 2000000,
    "core:version": "1.0.0"
  },
  "captures": [
    {"core:sample_start": 0, "core:frequency": 433920000}
  ],
  "annotations": []
}
```

`ci8_le` = complex int8, little-endian = `.cs8`. That's the format
H4CKRF uses natively.

For CTF-authored puzzles: **please annotate**. `annotations` can
tag byte ranges with hints ("this is the preamble", "this burst is
different"). The H4CKRF decoders don't currently read SigMF
annotations — that's a corpus-only feature — but URH does, and
future H4CKRF work may.

---

## Metadata sidecar (H4CKRF native)

`capture_iq` writes a JSON sidecar next to every `.iq` file with the
metadata that gets otherwise lost:

- `center_freq_hz` — what the tuner was set to
- `target_freq_hz` — the frequency of interest (if given)
- `sample_rate_hz`
- `duration_s`
- `lna_gain_db`, `vga_gain_db`, `rf_amp_db`
- `timestamp` (UTC ISO)
- `session_id`

The sidecar makes captures self-describing — you can hand one to a
teammate and they can pass it into any decoder without needing to
know the tune.

---

## Troubleshooting IQ files

### "iq file too large" from a decoder

You exceeded `MAX_IQ_FILE_BYTES` (1 GiB). Either:
- Recapture at a lower sample rate or shorter duration.
- Split the file: `split -b 1G capture.iq capture-`.

### The spectrogram is upside-down / mirrored

Byte-swapped file (big-endian). Convert:

```python
import numpy as np
data = np.fromfile('capture.iq', dtype='>i2').astype('<i2')  # for cs16
data.tofile('capture.iq')
```

For `.cs8` this doesn't apply — 8-bit types have no endianness.
A mirror-image spectrum with `.cs8` usually means I/Q swap; swap
the channels:

```python
import numpy as np
s = np.fromfile('capture.cs8', dtype=np.int8)
s[::2], s[1::2] = s[1::2].copy(), s[::2].copy()
s.tofile('capture-swapped.cs8')
```

### Huge fake DC spike at 0 Hz

Two common causes:

1. **You tuned `center_freq_hz` to the frequency of interest.** The
   LO leaks a DC spike at the tuner center. Fix: recapture with
   `target_freq_hz` instead. The executor offsets the tuner by
   `sample_rate_hz / 4`.
2. **You loaded a `.cu8` file as `.cs8` and didn't subtract the
   127 bias.** Fix: convert (see above).

### Decoder returns nothing but the file has clear signal

- Wrong sample rate — pass what the file was captured at.
- Wrong symbol rate — try `analyze_iq_symbols` to estimate.
- Wrong polarity (Manchester) — try both `"ieee"` and `"g.e.thomas"`.
- Wrong center frequency — run `analyze_iq_carrier_frequency` to
  find the true offset.

---

## Cross-references

- [../knowledge/iq-formats/reference.md](../knowledge/iq-formats/reference.md) — full format table
- [../knowledge/sigmf-metadata/reference.md](../knowledge/sigmf-metadata/reference.md) — SigMF details
- [../knowledge/inspectrum/](../knowledge/inspectrum/) — Inspectrum walkthrough
- [../knowledge/gqrx-cubicsdr-sdrpp/](../knowledge/gqrx-cubicsdr-sdrpp/) — live receivers
- [ctf_recipes.md](ctf_recipes.md) — recipes that consume IQ files
- [troubleshooting.md](troubleshooting.md) — when a capture explodes on disk
