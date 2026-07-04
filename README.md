# gndctrl

**Ground Control for your codebase — zone-based stability annotations that any AI agent understands, enforced at runtime, from a single project to a full dev platform.**

---

## What It Is

gndctrl is a zone-based governance and enforcement layer for AI agents operating in codebases.

It gives your codebase a voice by annotating source files with zone markers that any agent, CI system, or tool can read. It enforces those annotations at runtime — blocking agents from touching locked zones, preventing two agents from conflicting in the same zone simultaneously, and requiring human clearance before sensitive areas are modified.

Think of it as **Air Traffic Control for your codebase.**

---

## Status

**Private / Pre-release.** Currently battle-testing inside [pChisel](https://github.com/internetsguy/pChisel) as the reference fleet mode implementation.

| Phase | Status |
|---|---|
| Spec v0.1.0 | ✓ Complete |
| Reference fleet implementation | ✓ Running in production |
| CLI (`init` · `audit` · `preflight` · `zones` · `lock`) | ✓ Built — runs from source |
| Per-edit read-gate hook (Claude Code) | ✓ Running in production |
| Dispatch gate + zone locks — all agents (Claude / Codex / Kilo) | ✓ Running in production (pChisel) |
| Commit-time gating (GitHub Action / pre-commit) | Planned |
| Provider adapters | Claude / Codex / Kilo contract-governed; per-edit hook is Claude-only |
| Published packages (PyPI / npm / curl) | Planned |
| Hosted platform (gndctrl.dev) | Planned |

---

## Repository Layout

```
gndctrl/
├── spec/               # The open standard — zone marker format, .gndctrl schema, stability tiers
├── src/gndctrl/        # The CLI package — parser, schema validator, auditor, preflight resolver
├── docs/               # how-it-works.md — the mechanism + why it beats a plain prompt file
├── cli/                # legacy entry stub (superseded by src/gndctrl)
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

## Install & use

The CLI works today, installed from source:

```bash
pip install -e .          # from the repo root
gndctrl init              # scaffold .gndctrl + logbook/ (auto-detects single vs fleet)
gndctrl audit             # validate markers, CRIDs, dependency integrity (exit 1 on errors)
gndctrl audit --format json   # CI-friendly output
gndctrl preflight --zones PAYMENT --agent-class heavy   # resolve deps + clearance
gndctrl zones             # list zones
```

Published installers are planned but not yet live:

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
