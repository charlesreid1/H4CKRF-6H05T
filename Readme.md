# H4CKRF-6H05T

H4CKRF-6H05T is a HackRF co-pilot: an RF/SIGINT knowledge corpus *and* a
safety-gated control plane exposed over MCP. It knows the canon (modulation
families, common ISM/UNII bands, keyfob and paging protocols, decoder pipelines)
and it can act — safely — on the HackRF One. Every RF action funnels through
one deterministic `execute_command` chokepoint that classifies risk, checks
grants, asks for approval, and audits the result. The LLM never touches
libhackrf.

Inspired by [M0MA-V3SP3R](https://github.com/charlesreid1/M0MA-V3SP3R) but for
HackRF, with a laptop running Python instead of an Android app on a phone.

---

## What can it do?

Three tiers, from knowing to analyzing to acting:

- **Know** — corpus tools (`knowledge_list_topics`, `knowledge_read`,
  `knowledge_search`, `knowledge_lookup_band`, `knowledge_lookup_modulation`,
  `knowledge_lookup_protocol`, `knowledge_verify_claim`). All read-only, all
  `LOW` risk, cannot cause RF emission. *[planned — see
  [plan-organization.md](plan-organization.md)]*
- **Analyze** — DSP tools that operate on already-captured `.iq` files
  (`read_iq_summary` today; `analyze_iq_modulation`, `analyze_iq_symbols`,
  `decode_manchester`, `decode_pwm`, `decode_pocsag`, `decode_ads_b` planned).
  Cannot touch hardware.
- **Act** — the existing HackRF surface (`get_device_info`, `sweep_spectrum`,
  `capture_iq`, `transmit_iq`, `grant_list`, `audit_query`, `decode_ook`).
  Every action goes through the funnel below.

---

## Safety funnel

Everything that could conceivably cause RF energy to leave the HackRF, or that
opens the USB handle, or that reads raw IQ from the device, funnels through
one deterministic chain:

```
ExecuteCommand → CommandExecutor.execute()
                    → RiskAssessor.assess()
                    → PermissionService.check() (for TX)
                    → ApprovalPort.request() (for MEDIUM/HIGH)
                    → HackrfDriver / HackrfSubprocess
```

There is no second MCP tool that reaches libhackrf. The LLM sees exactly one
tool, `execute_command`, discriminated by `action`. Knowledge and analysis
verbs land as new `CommandAction` values with fixed `LOW` risk — they inherit
the full audit trail and cannot bypass the gate. The funnel invariant is
stated in full in [plan-organization.md](plan-organization.md).

---

## ⚠️ Safety warning

**HackRF can transmit.** This software gates dangerous actions but does not
guarantee legality — you are responsible for FCC compliance (or your local
regulator) in your jurisdiction. Read
**[docs/safety.md](docs/safety.md)** before your first TX.

---

## Repo map

```
src/hackrf_agent/    the safety-gated MCP + CLI (installable Python package)
knowledge/           the RF/SIGINT corpus (markdown + records/*.json)
skills/hackrf/       the SKILL.md that tells an assistant to use the MCP
scripts/             user-facing shell/Python helpers (schema regen, fixtures)
docs/                long-form guides (architecture, safety, MCP host setup)
schemas/             JSON Schema for the execute_command envelope + records
tests/               unit + integration + mcp + e2e
```

See [plan-organization.md](plan-organization.md) for the reorganization plan
and [plan-knowledge.md](plan-knowledge.md) for the corpus contents.

---

## Quick Start

Get from a fresh laptop to an interactive HackRF chat session. Covers macOS and
Ubuntu.

### 0. What you need

- A HackRF One (rev A/B/C).
- A data-capable USB-A → USB-mini cable (charge-only cables won't enumerate).
- Python **3.11 or newer**.
- An OpenRouter API key (get one at [openrouter.ai](https://openrouter.ai/)).

### 1. Install the HackRF host tools + libhackrf

`pyhackrf` is a Python wrapper around the system `libhackrf` library. The
library must exist before `pip install` will work end-to-end, and the
`hackrf_info` / `hackrf_transfer` CLI tools are what `hackrf-agent doctor` uses
to prove the device is alive.

**macOS (Homebrew):**

```bash
brew install hackrf
```

This installs `libhackrf`, the `hackrf_*` CLI tools, and firmware images under
`$(brew --prefix)/share/hackrf/firmware/`.

**Ubuntu (22.04+):**

```bash
sudo apt update
sudo apt install hackrf libhackrf-dev libhackrf0
```

Install the udev rules so a non-root user can open the device:

```bash
sudo cp /usr/share/hackrf/53-hackrf.rules /etc/udev/rules.d/ 2>/dev/null || \
  sudo tee /etc/udev/rules.d/53-hackrf.rules > /dev/null <<'EOF'
ATTR{idVendor}=="1d50", ATTR{idProduct}=="6089", MODE="0666"
ATTR{idVendor}=="1d50", ATTR{idProduct}=="604b", MODE="0666"
ATTR{idVendor}=="1d50", ATTR{idProduct}=="cc15", MODE="0666"
EOF
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Unplug and replug the HackRF after the rules land.

### 2. Verify the device enumerates

Plug in the HackRF, then:

```bash
hackrf_info
```

You should see something like:

```
hackrf_info version: 2024.02.1
libhackrf version: 2024.02.1
Found HackRF
Index: 0
  Serial number: 0000000000000000c86463dc2f4b6a1f
  Board ID Number: 2 (HackRF One)
  Firmware Version: 2024.02.1 (API:1.08)
  Part ID Number: 0xa000cb3c 0x006b4762
```

If nothing appears:

- **macOS:** `system_profiler SPUSBDataType | grep -A 8 HackRF` to confirm the
  OS sees it. Try a different USB-A port (skip hubs and USB-C dongles for the
  first test).
- **Ubuntu:** `lsusb | grep 1d50` should show the device. If `hackrf_info`
  shows a permission error, the udev step above didn't take — replug or
  re-check the rules file.

**Firmware old?** Compare `Firmware Version` against the latest release at
[github.com/greatscottgadgets/hackrf/releases](https://github.com/greatscottgadgets/hackrf/releases).
To upgrade:

```bash
# macOS firmware lives here after `brew install hackrf`
hackrf_spiflash -w $(brew --prefix)/share/hackrf/firmware-bin/hackrf_one_usb.bin

# Ubuntu (path may vary by package version)
hackrf_spiflash -w /usr/share/hackrf/firmware-bin/hackrf_one_usb.bin
```

Then unplug/replug and rerun `hackrf_info`.

### 3. Clone and install `hackrf-agent`

```bash
git clone https://github.com/charlesreid1/H4CKRF-6H05T.git
cd H4CKRF-6H05T

python3.11 -m venv .venv
source .venv/bin/activate

pip install -e '.[dev]'
```

The `[dev]` extra pulls in `pyhackrf` (which links against the `libhackrf` you
installed in step 1) and the OpenAI SDK (for OpenRouter).

### 4. Export your OpenRouter API key

`hackrf-agent` reads `OPENROUTER_API_KEY` from the environment — nothing else.
Export it in your shell before launching the CLI:

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

Or keep the key in a git-ignored dotfile and `source` it per session:

```bash
# ~/.openrouter_api_key
export OPENROUTER_API_KEY=sk-or-v1-...
```

```bash
source ~/.openrouter_api_key
```

There is no `.env` auto-load — if the variable isn't in your shell environment,
`hackrf-agent doctor` and `hackrf-agent chat` will refuse to start.

#### Changing the model

The default model is `deepseek/deepseek-v4-pro` (defined once in
`src/hackrf_agent/ai/llm_client.py` as `DEFAULT_MODEL`). To use a different
OpenRouter model, create or edit `~/.hackrf-agent/config.toml`:

```toml
model = "anthropic/claude-sonnet-5"
```

This is read by the CLI on startup and passed to `OpenRouterClient`. In code,
you can also pass `model="..."` directly to the `OpenRouterClient` constructor.

### 5. Run the diagnostic

```bash
hackrf-agent doctor
```

All four checks (`home_dir`, `db_schema`, `api_key`, `hackrf`) should be green.
If `hackrf` is red but `hackrf_info` worked in step 2, your shell can't find
the CLI on `PATH` — `which hackrf_info` and adjust.

### 6. Start chatting

```bash
hackrf-agent chat
```

You're in an interactive REPL. Try:

```
> what firmware is on the device?
> sweep the 433 MHz ISM band for 500 ms and tell me the top three peaks
```

RX-only commands run unattended. MEDIUM-risk commands prompt `[y/N]`; HIGH-risk
commands require typing `CONFIRM`. **Ctrl-C** aborts the current operation
and revokes any active TX grants; pressing Ctrl-C a second time within 2 s
stops the event loop and exits the process.

Before ever transmitting, issue a scoped grant:

```bash
hackrf-agent grant tx 433.05-434.79M --for 30m --max-gain 20
```

…and read [docs/safety.md](docs/safety.md) first. Really.

---

## Use from an MCP host

`hackrf-agent-mcp` exposes the same safety-gated command surface as an MCP
server. Any MCP-aware host — Claude Desktop, Claude Code, Cursor, OpenCode,
`mcp-cli`, custom clients — can drive the radio through its tool, resource,
and elicitation surface.

```bash
hackrf-agent-mcp
```

Configure your host to spawn it on stdio. See
**[docs/mcp.md](docs/mcp.md)** for host config snippets, the full tool list,
how approval works over MCP elicitation, resource URIs, and safety caveats.

---

## Documentation

- **[docs/architecture.md](docs/architecture.md)** — how the pieces fit together.
  The layer diagram, module map, risk-tier table, envelope schema, audit-log
  schema, and data-flow for one command.
- **[docs/safety.md](docs/safety.md)** — what the risk gate does, and does not,
  protect. FCC citations, plain-English risk tiers, the grant model, the kill
  switch, and incident response.
- **[docs/execute_command_schema.md](docs/execute_command_schema.md)** — the
  LLM's one tool. One section per `CommandAction` with purpose, args, example,
  and risk tier. Auto-generated from the code.
- **[docs/mcp.md](docs/mcp.md)** — use HackRF from any MCP-aware host (Claude
  Desktop, Claude Code, Cursor, OpenCode, `mcp-cli`, …). Tool list, host config
  snippets, approval flow, resources, and safety caveats.
- **[docs/development.md](docs/development.md)** — contributor guide. Setup,
  test tiers, "add a new CommandAction" checklist, CI runners, release process.
- **[docs/cli.md](docs/cli.md)** — user-facing command reference.
- **[docs/ai-package.md](docs/ai-package.md)** — contributor reference for the
  `hackrf_agent.ai` package.
- **[docs/tests.md](docs/tests.md)** — how to run each test tier, and what the
  tiers mean.

---

## Architecture at a glance

```
CLOUD (OpenRouter)
    ↕  execute_command({action, args, justification, expected_effect})
LAPTOP (Python)
    HackrfAgent → CommandExecutor → RiskAssessor / PermissionService / ApprovalPort
    ↓  libhackrf via pyhackrf
HackRF One (USB peripheral)
```

The LLM never touches the USB handle, never sees raw IQ, and never
self-classifies risk. Every `execute_command` passes through one deterministic
funnel.

---

## License

MIT — see [LICENSE](LICENSE).
