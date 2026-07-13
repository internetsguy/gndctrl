# gndctrl

**Ground Control for your codebase — zone-based stability annotations that any AI agent understands, enforced at runtime, from a single project to a full dev platform.**

I started this project initially to just stop my agents from drifting and wasting tokens but it's evolved into much more than that now and I've been using it to create tools that have some serious structure much faster than if I wasn't using it. I'm sure there's other things like it out there now but this is my take on overcoming an issue I found and I'm really happy to get feedback about whether it helps anyone out and if there's anything huge I missed
---

## What It Is

gndctrl is a zone-based governance and enforcement layer for AI agents operating in codebases.

It gives your codebase a voice by annotating source files with zone markers that any agent, CI system, or tool can read. It enforces those annotations at runtime — blocking agents from touching locked zones, preventing two agents from conflicting in the same zone simultaneously, and requiring human clearance before sensitive areas are modified.

Think of it as **Air Traffic Control for your codebase.**

---

## Status

**Pre-release.** Battle-tested and hardened inside **pyChisel** — a production multi-tenant AI dev platform — as the reference fleet-mode implementation.

| Phase | Status |
|---|---|
| Spec v0.1.0 | ✓ Complete |
| Reference fleet implementation | ✓ Running in production |
| CLI (`init` · `audit` · `preflight` · `zones` · `lock`) | ✓ Built — runs from source |
| **Air Traffic Control** — edit gate + ops gate (Claude Code hooks) | ✓ Shipped — `hooks/`, installed by `install.sh` |
| Dispatch gate + zone locks — all agents (Claude / Codex / Kilo) | ✓ Running in production (pyChisel) |
| Commit-time gating (GitHub Action / pre-commit) | Planned |
| Provider adapters | Claude / Codex / Kilo contract-governed; ATC hooks are Claude-only |
| `curl \| bash` installer (CLI + ATC hooks) | ✓ `install.sh` |
| Published packages (PyPI / npm) + `gndctrl.dev` vanity URL | Planned |
| Hosted platform (gndctrl.dev) | Planned |

---

## Repository Layout

```
gndctrl/
├── spec/               # The open standard — zone marker format, .gndctrl schema, stability tiers
├── src/gndctrl/        # The CLI package — parser, schema validator, auditor, preflight resolver
├── docs/               # how-it-works.md — the mechanism + why it beats a plain prompt file
├── cli/                # legacy entry stub (superseded by src/gndctrl)
├── hooks/              # Air Traffic Control — the PreToolUse enforcement hooks (edit gate + ops gate)
├── adapters/           # Provider-specific agent contract templates
│   ├── claude/         # Claude Code + Claude API contracts (done)
│   ├── gemini/         # Gemini CLI adapter (planned)
│   ├── codex/          # OpenAI Codex adapter (planned)
│   └── gitagent/       # GitAgent export format (planned)
├── docker/             # Docker-native install — sidecar + entrypoint injection (planned)
└── github-action/      # PR zone validation — block merges touching locked zones (planned)
```

---

## Quick Concept

```python
# @gndctrl:zone START | id=PAYMENT | stability=sensitive | type=code | minimum_agent_class=heavy
# @gndctrl:node id=PAYMENT.process_charge | risk=high | touches=[stripe_api, ledger] | crid=PAY-20260323-001
async def process_charge(amount: int, customer_id: str) -> dict:
    ...
# @gndctrl:zone END | id=PAYMENT
```

An agent hitting this zone:
1. Checks its weight class against `minimum_agent_class=heavy`
2. Loads the full PAYMENT zone doc before touching anything
3. Reads the logbook entry for `PAY-20260323-001`
4. Surfaces a risk summary before proceeding
5. Cannot enter if the zone is locked by another agent

---

## Scale Modes

**Single mode** — one `.gndctrl` file at the project root. Works immediately with no other setup.

**Fleet mode** — a master `.gndctrl` governs multiple projects. Each project has an airspace ID. Cross-project dependencies are tracked and enforced.

The same marker syntax, same stability tiers, same agent contracts. Scale is a configuration choice, not a conceptual shift.

In both modes, runtime zone-lock state lives in a machine-managed `.gndctrl.locks` file (gitignored) — never in the `.gndctrl` document itself, which stays byte-stable so agent runtimes can cache it. See the *Cache-Stable Documents* section of the spec.

---

## Air Traffic Control — mechanical enforcement

Zone markers are only advice until something *makes* an agent read them. **Air Traffic
Control (ATC)** is that something: two [Claude Code](https://claude.com/claude-code)
`PreToolUse` hooks (in [`hooks/`](hooks/)) that deny a tool call until the governing
`.gndctrl` has actually been read in the current session. The agent reads the zone, then
retries — the user is never prompted. This is what turns "read the governing document
before you act" from prose nobody follows into a tripwire that self-corrects.

| Gate | Hook | Denies until the governing doc is read, for… |
|---|---|---|
| **Edit gate** | [`hooks/atc-edit-gate.py`](hooks/atc-edit-gate.py) | any `Edit`/`Write`/`NotebookEdit` to a file inside a gndctrl-governed project |
| **Ops gate** | [`hooks/atc-ops-gate.py`](hooks/atc-ops-gate.py) | any `Bash` command matching a governed **ops hazard** (a service restart, DNS reload, destructive recreate) |

The edit gate is **zero-config** — it reads the `*.gndctrl` files already in your repos.
The ops gate is **data-driven** — you list your platform's dangerous commands in
`~/.claude/atc-ops-hazards.json` and never touch the hook. Both **fail open** on any
internal error (a hook bug must never brick your session) and **fail closed** only on the
deterministic "you didn't read it" case. Per-command escape hatches: `ATC_EDIT_GATE_OFF=1`,
`ATC_OPS_GATE_OFF=1`. Full details in **[hooks/README.md](hooks/README.md)**.

---

## Install & use

One command installs the CLI **and** wires Air Traffic Control into `~/.claude/settings.json`
(idempotent — it preserves any existing config):

```bash
curl -fsSL https://raw.githubusercontent.com/internetsguy/gndctrl/master/install.sh | bash
```

Or from a clone:

```bash
pip install -e .          # from the repo root — the CLI
./install.sh              # CLI + Air Traffic Control hooks
```

Then, in any project:

```bash
gndctrl init              # scaffold .gndctrl + logbook/ (auto-detects single vs fleet)
gndctrl audit             # validate markers, CRIDs, dependency integrity (exit 1 on errors)
gndctrl audit --format json   # CI-friendly output
gndctrl preflight --zones PAYMENT --agent-class heavy   # resolve deps + clearance
gndctrl zones             # list zones
```

Published package managers + a vanity install URL are planned but not yet live:

```bash
# planned — not available yet
pip install gndctrl
npm install -g gndctrl
curl -fsSL https://gndctrl.dev/install.sh | sh
```

---

## Docs

- **[docs/how-it-works.md](docs/how-it-works.md)** — the full mechanism, why it beats a plain
  prompt file, the "it's software, not a prompt" breakdown, and the token-economy data.
- **Spec:** [`spec/gndctrl-spec-v0.1.0.md`](spec/gndctrl-spec-v0.1.0.md)

---

## Licence

Licensed under the **Apache License 2.0** — see [LICENSE](LICENSE).
