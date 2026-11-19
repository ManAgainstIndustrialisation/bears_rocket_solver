---
disclosure-default: ai-assisted
models-used:
  - gemini-3-8-flash
  - claude-opus-5-5
providers:
  - Google
  - Anthropic
scope: |
  Code mostly AI-generated with strict human verification; Documentation mostly
  human-written with some minor AI use. Claude Opus 5.5 (via Claude Code)
  authored the code cleanup, the BEARS_Isentropic module and the physical
  constants refactor described below
last-updated: 2026-11-19
---

# AI Disclosure

This repository follows the
[ai-disclosure convention](https://github.com/ggfevans/ai-disclosure).
See per-file headers for overrides.

## Claude Opus 5.5 contributions

Claude Opus 5.5 (Anthropic), working through Claude Code, wrote the following
changes. A human requested and reviewed them. Every change was checked by
running the solver against a saved baseline before it was committed.

- **Code and input cleanup.**
  - Strict config loading that rejects unknown keys.
  - Inputs that were loaded but never applied now take effect, and unused
    ones are removed.
  - Bug fixes in config validation, the RocketCEA backend, the run checks and
    both test stands.
  - Dead code and duplicated code removed, with the shared output code moved
    to `modules/BEARS_Rocket/reporting.py`.
  - A `--sweep` flag added to `solver.py`.
- **`modules/BEARS_Isentropic/`** (whole package, AI-generated).
  - Isentropic flow relations and their inverses, plus a calculator-style
    `IsentropicState`.
  - Implements the NASA Glenn Beginner's Guide to Aeronautics isentropic flow
    page and the BGA calculator's outputs.
  - Checked against standard gamma = 1.4 tables.
- **Physical constants refactor.**
  - `inputs/constants.toml` and `modules/Config/constants.py` added.
  - Every hardcoded physical constant and `scipy.constants` import replaced
    with values loaded from `inputs/constants.toml`.
  - The built-in material and gas presets removed, so materials and gases now
    come from the input files.
  - The oxidizer vapor pressure turned into the input
    `oxidizer_tank.vapor_pressure_bar`.
