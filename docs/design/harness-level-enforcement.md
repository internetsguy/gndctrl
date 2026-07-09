# Design note — harness-level enforcement (all agents)

**Status:** Design note · depends on `gndctrl preflight --task`

## Problem

gndctrl enforcement is two-tier: the **contract text** reaches all agents (Codex/ChatGPT, Kilo,
Claude, Gemini, Copilot — one file, several install paths), but the **hard gate** (deny an edit
until the governing `.gndctrl` is read) ships as a Claude Code PreToolUse hook and applies to
Claude only. Codex, Kilo, and Gemini are governed by honor system.

If most of your users start on a provider *without* a hard gate, the most-used agent is the
*least* enforced. That's backwards.

## The approach — gate at the dispatch point

If your platform runs agents through a **single dispatch handler** — one place that spawns the
provider CLI for a turn, in the project workspace — that handler is the one place to gate *all*
agents identically, without touching any agent's own config. (This is exactly what the pChisel
reference deployment does: every provider path funnels through one chat handler, so gating there
governs Codex, Kilo, and Claude in one stroke.)

## Design

Before spawning the provider CLI for a turn, the handler runs:

```
gndctrl preflight --task "<user message>" --agent-class <declared> --format json
```

and branches on the clearance:

- `cleared` → inject `required_reads` + `constraints` into the prompt preamble, then dispatch.
- `denied` (weight class) / `held_locked` → do **not** dispatch; return the `user_summary` to the
  chat as the assistant turn ("this touches a locked zone — here's why, and what to do").
- `ambiguous` / `ungoverned` → dispatch normally (no `.gndctrl`, or task didn't map to a zone).

This makes enforcement **provider-agnostic**: identical gating for Codex, Kilo, Claude, Gemini —
enforcement lives in the harness, not in per-agent hook machinery. A per-provider hook (like the
Claude PreToolUse edit-gate) can stay as defense-in-depth or be retired once the harness gate is
proven.

## Prerequisites

1. `gndctrl preflight --task` (see `design-preflight-task.md`).
2. A declared agent-class per session (the platform knows which model is connected; map it to a
   weight class at dispatch — the contract already frames class as *declared, not inferred*).
3. Confirm each provider actually loads the contract from the workspace (native `AGENTS.md`
   support) or inject it into that provider's prompt at dispatch.

## Verification when built

The same task ("edit a file in a `locked` zone") issued via every provider must be refused at
dispatch with the same `user_summary`, before any file write.
