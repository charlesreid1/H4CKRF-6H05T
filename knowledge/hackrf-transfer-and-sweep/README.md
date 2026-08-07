# hackrf-transfer-and-sweep — the vendor CLI

Great Scott Gadgets ships three small CLIs alongside the HackRF firmware:
`hackrf_transfer` (RX/TX from/to file), `hackrf_sweep` (wideband peak
scan), and `hackrf_info` (device enumeration). The MCP wraps this
surface — most operators never call these directly, but knowing the
raw commands helps when things go wrong.
