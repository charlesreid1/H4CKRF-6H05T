# H4CKRF-6H05T

AI control plane for HackRF One — the LLM proposes RF actions; a deterministic
host-side gate authorizes or refuses each one; every step is audited.

Inspired by [M0MA-V3SP3R](https://github.com/charlesreid1/M0MA-V3SP3R) but for
HackRF, with a laptop running Python instead of an Android app on a phone.

---

## ⚠️ Safety warning

**HackRF can transmit.** This software gates dangerous actions but does not
guarantee legality — you are responsible for FCC compliance (or your local
regulator) in your jurisdiction. Read
**[docs/safety.md](docs/safety.md)** before your first TX.

---

## Quick-start

Get from a fresh laptop to an interactive HackRF chat session. Covers macOS and
Ubuntu; ~10 minutes if your HackRF is already flashed with recent firmware.

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

### 4. Store your OpenRouter API key

Copy the example env file and drop your key in:

```bash
cp .env.example .env
$EDITOR .env    # replace the placeholder with your real key
```

`.env` is git-ignored. `hackrf-agent` auto-loads it from the current working
directory on startup, so as long as you launch the CLI from the repo root your
key is picked up.

Prefer to skip the file? Just export the variable in your shell:

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

An already-set `OPENROUTER_API_KEY` always wins over the `.env` file.

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
and revokes any active TX grants — double-tap within 2 s for a hard exit.

Before ever transmitting, issue a scoped grant:

```bash
hackrf-agent grant tx 433.05-434.79M --for 30m --max-gain 20
```

…and read [docs/safety.md](docs/safety.md) first. Really.

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
