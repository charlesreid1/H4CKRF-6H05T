# scripts/

Human-once helpers for maintaining the repo. You run these by hand when the
code they touch needs a refresh — they are not part of the MCP server or the
CLI's runtime path.

- **`generate_execute_command_schema.py`** — regenerate
  `docs/execute_command_schema.md` and `schemas/execute_command.schema.json`
  after adding or renaming a `CommandAction`. Run it once per PR that
  changes the action set.
- **`generate_tone_iq.py`** — author test fixtures: synthetic tone IQ files
  used by the DSP unit tests and the AI-side prompt examples.

Runtime code — the MCP server, the CLI, the safety funnel — lives in
`src/hackrf_agent/`. `scripts/` and `src/` are deliberately separate because
they have different audiences (human-once vs. runtime-always). Do not import
from `scripts/` inside the package.
