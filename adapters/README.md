# Adapters — installing the gndctrl contract per agent

**Canonical contract text lives in [`../docs/contracts/`](../docs/contracts/)** —
`single-mode-contract.md` and `fleet-mode-contract.md`. This directory used to hold per-agent
copies; those were removed 2026-07-04 after they drifted from the spec (duplicate copies rot —
install FROM the canonical files instead).

## Install matrix

The contract is agent-agnostic markdown. Governance works with any agent that loads a
project-context file; install the mode contract (plus your deployment's platform rules) at the
path each agent reads:

| Agent | Context file it reads | Notes |
|---|---|---|
| OpenAI Codex CLI (ChatGPT) | `<project>/AGENTS.md` | **Native convention** — `AGENTS.md` support is built into the CLI. |
| Kilo CLI | `<project>/AGENTS.md` | Reads `AGENTS.md` natively (verified against the shipped binaries). |
| Claude Code | `~/.claude/CLAUDE.md` or `<project>/CLAUDE.md` | Also supports **hard enforcement** via a PreToolUse hook that denies edits until the `.gndctrl` is read — see the pChisel reference hooks (`gndctrl-preflight.py`, `gndctrl-session.py`). |
| Gemini CLI | `~/.gemini/GEMINI.md` or `<project>/GEMINI.md` | |
| GitHub Copilot | `<project>/.github/copilot-instructions.md` | |
| Qwen Code | `<project>/QWEN.md` (also honors `AGENTS.md` in recent versions) | |
| Anything else | Its system-prompt / rules file | The contract is plain markdown — paste it wherever the agent takes standing instructions. |

One source file, many install paths — a deployment script should `cp` from
`docs/contracts/<mode>-mode-contract.md` to each path (see the pChisel reference deployment:
`chisel-base/entrypoint.sh` seeds four paths per container from one file, and verifies with a
single md5 across all copies).

## Enforcement levels

| Level | What provides it | Agents covered |
|---|---|---|
| **Contract text** (honor system) | The markdown files above | All of them |
| **Hook gate** (hard deny before edit) | Claude Code PreToolUse hook | Claude Code only |
| **Harness gate** (hard deny at dispatch) | Run `gndctrl preflight --task` (Phase 5, see `../docs/design/`) in the platform that launches the agent; refuse dispatch on non-zero clearance | Any agent, any provider — enforcement lives in the harness, not the agent |

The harness gate is the intended end-state for multi-agent deployments: one check in the
launcher governs every provider identically, with no per-agent hook machinery.
