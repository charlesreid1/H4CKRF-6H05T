# transmit-pipeline/walkthrough.md — end-to-end example

Scenario: operator has generated `keyfob_fixture.cs8` and wants to
transmit it at 433.92 MHz on their own hardware in a screen room.

## Step 1 — operator requests a grant

```
request_permission_grant({
  freq_range_hz: [433900000, 433950000],
  max_tx_vga_db: 12,
  duration_minutes: 5,
  justification: "keyfob fixture bench test - own hardware"
})
```

**Prompt to human:** "Approve TX grant on 433.90-433.95 MHz at up to
12 dB VGA for 5 minutes? Reason: keyfob fixture bench test."

Human clicks yes. Grant issued.

## Step 2 — operator issues transmit_iq

```
transmit_iq({
  iq_path: "session/keyfob_fixture.cs8",
  freq_hz: 433920000,
  tx_vga_db: 10,
  sample_rate_hz: 2000000
})
```

## Step 3 — MCP pipeline

1. **Path validation:** `session/keyfob_fixture.cs8` resolves under
   `SessionPaths.session_dir()`. ✓
2. **Grant coverage:** `433920000` ∈ `[433900000, 433950000]` and
   `10 <= 12`. ✓
3. **RiskAssessor gate:** 433.92 MHz is not in the BLOCKED table. ✓
4. **Capture-time budget:** cumulative TX + capture time is under
   `MAX_CAPTURE_MINUTES`. ✓
5. **Approval prompt:** since a valid grant covers this call, no
   further human prompt is required (grant pre-approved).
6. **HackRF driver:** shell out to
   `hackrf_transfer -t session/keyfob_fixture.cs8 -f 433920000
   -s 2000000 -x 10`.

## Step 4 — audit trail

- MCP writes an audit entry:
  `{timestamp, action: "transmit_iq", freq: 433920000, tx_vga: 10,
   duration_s: <computed from file length / sample rate>,
   grant_id: <the grant's id>, hash: <sha256 of iq file>}`.

## Failure modes

- **Path traversal attempt:** `iq_path: "../../etc/passwd"` → path
  validation fails → refused before touching hardware.
- **Grant miss:** `freq_hz: 315000000` with a 433 MHz grant → grant
  coverage fails → refused.
- **BLOCKED band:** `freq_hz: 1090000000` (ADS-B) → RiskAssessor
  refuses regardless of grant → refused.
- **Over-budget:** cumulative TX has exhausted `MAX_CAPTURE_MINUTES`
  → refused with a "session budget exhausted" error.
- **VGA over-max in grant:** `tx_vga_db: 30` with grant max 12 → grant
  coverage fails → refused.

## For research

The transmit-pipeline enforces the safety funnel invariant: **the LLM
cannot circumvent the risk gate or the grant.** Even a maliciously
crafted `transmit_iq` call whose parameters look reasonable is refused
if any check in the pipeline fails. This is the "acting half" of the
co-pilot; the knowledge corpus is the "knowing half."
