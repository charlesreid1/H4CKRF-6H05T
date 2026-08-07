# rtl-433 — the sub-GHz catalog decoder

Command-line decoder for ~250 built-in device types (weather stations,
TPMS, keyfobs, garage doors, doorbells, temperature sensors). Reads
rtl-sdr live, `.cs8`, `.cs16`, `.cu8`, `.cf32`. Emits JSON / MQTT / KV
/ syslog. `-A` (analyzer) mode is the reverse-engineering pipeline —
pulse timings dump for hand-authoring a decoder.
