# Field Kit

Getting from "we're going to an RF village" to "we're actually
solving challenges" in the parking lot. This doc is the pre-event
checklist and the on-site fallback playbook.

Not covered here: what the tools *do*. See
[ctf_playbook.md](ctf_playbook.md) and
[ctf_recipes.md](ctf_recipes.md) for that.

---

## The bag

### Radio + interconnect

- **HackRF One** (rev A/B/C). Confirm firmware ≥ 2024.02 with
  `hackrf_info` before you leave; upgrading in a hotel room on venue
  wifi is not fun. Firmware flash instructions are in
  [../Readme.md](../Readme.md).
- **USB-A → USB-mini** data-capable cable, **plus one spare**. Cables
  fail. The 6-inch ones from AliExpress fail early.
- **Powered USB-A hub** for laptops that only have USB-C. The HackRF
  pulls ~500 mA under load; unpowered USB-C dongles brown out.
- **USB extension cable, 1–2 m** — puts the HackRF's mixer noise away
  from the laptop's switching supplies. Real gain, especially at ISM
  433.

### Antennas (bring at least three)

The stock ANT500 telescoping antenna is a compromise for everything
and optimal for nothing. Bring band-specific ones for the frequencies
you actually plan to work in.

Quarter-wave monopole length: `λ/4 = 75 / f_MHz` cm.

| Frequency | λ/4 | What to bring |
|---|---|---|
| 315 MHz | 23.8 cm | ANT500 extended, or a 24 cm whip |
| 433 MHz | 17.3 cm | 17 cm whip (very common ISM antenna) |
| 868/915 MHz | 8.6 / 8.2 cm | 8 cm whip; many "LoRa antennas" work |
| 1090 MHz (ADS-B) | 6.9 cm | Dedicated 1090 filter+LNA if serious |
| 2.4 GHz | 3.1 cm | Rubber duck, or WiFi antenna via RP-SMA↔SMA |

Full antenna zoo (dipoles, discones, log-periodics, biquads) is in
[../knowledge/antennas/reference.md](../knowledge/antennas/reference.md).

**Connector caveat.** HackRF One uses **SMA female**. Most cheap WiFi
antennas are **RP-SMA**. They will thread together but not make
contact. Bring an SMA↔RP-SMA adapter or you'll be sad.

### Optional but worth the weight

- **NanoVNA** (~$50). Verifies antenna VSWR on-site. VSWR > 2.0 =
  wasting TX power into your amplifier.
- **External LNA** for weak signals (ADS-B especially). Watch for
  saturation — turn HackRF's built-in `rf_amp_db` **off** when
  chaining external gain.
- **Bandpass filter** for the target band. Helps with strong out-of-band
  interferers (WiFi splatter, cell tower a block away).
- **Battery pack** for the laptop. Venue outlets are gold-standard
  scarce.

---

## Pre-event: home rehearsal (do this the night before)

Full run against your target puzzle shapes. If any of these fail at
home, they'll definitely fail in a loud room.

### 1. `doctor --strict` green

```bash
hackrf-agent doctor --strict
```

All checks OK. If `firmware` is a warning, you're probably fine but
know the string in case a decoder misbehaves.

### 2. Baseline sweep + capture

```bash
hackrf-agent chat
> sweep 433 to 434 MHz for 1 second
> capture 2 seconds at 433.92 MHz, 2 Msps
> summarize that IQ file
```

Every step should succeed silently (LOW tier, no prompt).

### 3. Elicitation flow

```
> sweep 433 to 434 for 10 seconds  # MEDIUM
```

Approve prompt should appear. Approve once, deny once, so you know
what both look like. Then:

```
> transmit a 1-second tone at 433.92 MHz, 10 dB TX gain, from <iq_file>  # HIGH
```

You should be asked to type `CONFIRM`. Deny it — this is a rehearsal.

### 4. BLOCKED wall

```
> transmit anything at 1575 MHz
```

Must refuse before touching hardware. If it doesn't, **stop and file
a bug** — do not go to the event.

### 5. Grant → reclassify

```bash
hackrf-agent grant tx 433.05-434.79M --for 10m --max-gain 20
```

Then retry step 3's TX. It should now execute as LOW.

### 6. Kill switch

Start a long capture. Ctrl-C once. Grants should be revoked; the
process should stay alive. `hackrf-agent grant list` should be empty.

### 7. Save a "known-good" state

```bash
tar -czf ~/hackrf-agent-known-good.tar.gz ~/.hackrf-agent/config.toml
```

If the venue laptop's state gets corrupted mid-event, you can
restore config to a working baseline.

---

## Offline / venue-wifi survival

DEF CON wifi is famously hostile. Assume no internet. Two things
depend on it in H4CKRF:

1. **OpenRouter** — the chat CLI needs `OPENROUTER_API_KEY` to work
   at all. No network = no chat REPL.
2. **`pip install`** — anything you didn't install before the flight
   is not going to install now.

### What works offline

- The **MCP server** (`hackrf-agent-mcp`) runs entirely locally. It
  never makes outbound API calls. If your MCP host is also local
  (a self-hosted assistant, `mcp-cli`), the whole stack works
  air-gapped.
- The **knowledge corpus** (`hackrf-agent lore` / all
  `knowledge_lookup_*` verbs) is on disk. Zero network needed.
- The **DSP tier** (`analyze_iq_*`, `decode_*`) runs on captured
  files entirely locally.
- **`hackrf-agent grant`, `audit`, `doctor`** are all local.

### What doesn't

- `hackrf-agent chat` — requires OpenRouter.
- Any MCP host that funnels through a cloud API (Claude Desktop,
  Claude Code with a cloud-only model).

### Fallback recipe: no chat, no cloud host, still hunting

You can drive the whole safety funnel from the command line without
any LLM.

```bash
# Ask the corpus what's on a frequency
hackrf-agent lore lookup-band 433920000

# Sweep, capture, analyze — all via the CLI (no chat)
# (These verbs don't have direct CLI subcommands today; drive them
# via `hackrf-agent-mcp` + `mcp-cli --stdio`.)
mcp-cli --stdio -- hackrf-agent-mcp
```

The `mcp-cli` REPL exposes every tool by name. Slower to drive, but
zero LLM in the loop and zero network dependency.

### Cached model fallback

If your MCP host supports a local model (Ollama, LM Studio,
llama.cpp), configure it before you leave. Tool-calling quality
varies wildly across local models; test with a rehearsal round.

---

## RF hygiene at the venue

- **RF village is a swamp.** Dozens of HackRFs, hundreds of phones,
  villages full of 2.4 GHz WiFi + Bluetooth + Zigbee, plus whatever
  the organizers are transmitting on purpose. **Every capture will
  have interferers.** Widen LNA gain sparingly — you'll saturate on
  a nearby TX before you get the target.
- **Weak signal ≠ far away.** It might just be behind you. Point the
  antenna, rotate 90°, see if the peak in `sweep_spectrum` changes.
- **Test your antenna on a known signal.** FM broadcast at ~100 MHz
  is always there. If your antenna doesn't show FM stations,
  something upstream is broken (cable, adapter, LNA power).
- **Cellular downlink is a wall.** In dense areas you'll see
  splatter into the 800/900 ISM bands. Bandpass filter or gain
  reduction is the fix.

## Power + laptop

- **Screen brightness kills batteries.** Dim the laptop; expect
  ~2–3 h on battery under HackRF load.
- **HackRF draws ~500 mA sustained.** A powered hub is worth the
  extra cable.
- **Disable USB power saving** on Linux (`echo on >
  /sys/bus/usb/devices/*/power/control`) — some kernels suspend the
  HackRF mid-capture.

---

## Legal + venue rules

- **Follow the village rules first.** Even in ISM, DEF CON and other
  events have "no TX" or "TX only in taped-off area" rules. Their
  rules override [safety.md](safety.md).
- **You are responsible for FCC compliance** regardless of what
  H4CKRF permits. The gate is technical, not legal.
- **Never TX in a BLOCKED band.** Not even "briefly." Not even
  "just to test." The gate will refuse and it is correct to refuse.
- **RX is legal everywhere in the US** (with a few exceptions —
  encrypted cellular, some corporate two-way). RX regulation varies
  in other countries; know your jurisdiction if you're travelling.

---

## Pre-flight checklist (day of)

Print this. Or memorize it.

- [ ] HackRF, cable, spare cable
- [ ] Antennas for target bands + adapters
- [ ] Laptop, power brick, USB hub
- [ ] `hackrf-agent doctor --strict` green at home
- [ ] Known-good config backed up
- [ ] `OPENROUTER_API_KEY` in shell rc (if you're using chat)
- [ ] MCP host installed and configured
- [ ] `~/.hackrf-agent/` fits under whatever `MAX_CAPTURE_MINUTES`
      you plan to set — clear old captures if not
- [ ] Grant plan for any TX you know you'll do
- [ ] BLOCKED band list read + understood
- [ ] Kill-switch reflex: single Ctrl-C, single Ctrl-C, single Ctrl-C

---

## Cross-references

- [Readme.md](../Readme.md) — install
- [safety.md](safety.md) — bands, tiers, budgets
- [troubleshooting.md](troubleshooting.md) — when it breaks
- [ctf_recipes.md](ctf_recipes.md) — worked walkthroughs
- [../knowledge/antennas/reference.md](../knowledge/antennas/reference.md) — antenna zoo
- [../knowledge/hackrf-hardware/reference.md](../knowledge/hackrf-hardware/reference.md) — HackRF internals
