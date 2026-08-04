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

```bash
pip install -e '.[dev]'
hackrf-agent doctor
hackrf-agent chat
```

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
CLOUD (Claude / OpenRouter)
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
