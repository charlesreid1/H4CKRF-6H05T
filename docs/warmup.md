# HackRF Agent — Warm-up Sequence

Safe stuff first, then work up to the approval-gated calls so you can see the elicitation flow.

## 1. Smoke test (LOW, no approval)

- "Use the `hackrf_get_device_info` tool." — confirms the driver opens the radio and the session ID lands in the response.
- "Read `hackrf://sessions/current`." — sanity-checks resource wiring.

## 2. Read-only RX (LOW)

- "Sweep 433–434 MHz for 1 second at 20 dB LNA / 20 dB VGA." — short dwell keeps it in LOW tier, no prompt.
- "Capture 2 seconds of IQ at 433.92 MHz, 8 MHz sample rate." — should return an on-disk path under `~/.hackrf-agent/sessions/<id>/iq/`.
- "Summarize that IQ file with `hackrf_read_iq_summary`." — feed it the path from the previous call; verifies the tool chain works end-to-end.

## 3. Trigger a MEDIUM approval

- "Sweep 433–434 MHz for 10 seconds." — dwell > 2 s pushes it into MEDIUM. You should see Claude Code render an approve/deny prompt. Deny once, then re-run and approve, to see both paths.

## 4. Trigger a HIGH approval

- "Transmit a 1-second tone at 433.92 MHz, 10 dB TX gain, from `<some iq file>`." — ISM band + TX = HIGH; the prompt should also require you to type `CONFIRM`. Type something else first to confirm it's treated as denial.

## 5. Verify the BLOCKED wall

- "Transmit anything at 1575.42 MHz." — GPS L1, protected band. Should refuse before any hardware touch, with a clear reason.
- "Sweep with LNA gain 99." — out-of-range arg, should be rejected by the Pydantic layer.

## 6. Audit + grants

- "Query the last 20 audit rows with `hackrf_audit_query`." — you should see every step above logged.
- "Read `hackrf://audit/recent?limit=20`." — same data via the resource surface, good for cache-testing.
- "List active grants." — should be empty unless you've run `hackrf-agent grant tx ...` in a shell.

## 7. Grant → reclassify (optional)

- In a terminal: `hackrf-agent grant tx --band ism-433 --max-gain 20 --duration 10m`.
- Back in Claude: retry the ISM TX from step 4. It should now execute as LOW with no prompt. Watch for the grant to show up in `hackrf://grants/active`.

## 8. Signal handling (optional, terminal-side)

- Kick off a long capture, then `kill -INT` the `hackrf-agent-mcp` pid once. The current call should abort with an error but the server should stay up. A second SIGINT within 2 s exits.

---

If any step misbehaves, run `HACKRF_MCP_LOG_LEVEL=DEBUG hackrf-agent-mcp` and re-launch Claude Code with `--mcp-debug` to see both sides of the wire.
