# AGENTS.md — instructions for AI agents working in or installing gndctrl

## If you were asked to INSTALL gndctrl into a project

Follow `docs/AGENT-SETUP.md` exactly. It is a seven-phase runbook where every phase
gates on a VERIFY command — a step is complete when its VERIFY passes, never on the
strength of your own summary. Non-negotiables from it:

- A registry still containing `EXAMPLE_ZONE` is not an installed system; writing the
  real zone map (Phase 3) is the actual work, and the user confirms tier assignments.
- Never lower a zone's stability, delete a zone, or edit a hazard to make a check pass.
- The live-fire self test (Phase 6) needs a NEW session — the session that ran the
  installer is not protected by the hooks it just installed.
- Setup ends with the Phase 7 report to the user, including what is NOT enforced.

## If you are WORKING in a project governed by gndctrl

Follow the agent contract: `docs/contracts/single-mode-contract.md` (or
`fleet-mode-contract.md` if a master document is present). The short version:

1. Before editing any file, read the governing `*.gndctrl` — the zone registry entry
   for that file, its gotchas, and relevant logbook entries. Enforcement is mechanical
   on Claude Code (a PreToolUse gate denies unread edits); on other runtimes this
   contract is the enforcement.
2. `stability: locked` zones are human-clearance-only. Do not edit them, do not retry
   a denied edit, and do not change the zone's stability to proceed — present a diff
   to the user instead.
3. One agent per zone at a time — respect `.gndctrl.locks`.
4. After meaningful changes, update the zone's gotchas/logbook so the next agent
   inherits what you learned.

## If you are DEVELOPING gndctrl itself

Read `docs/how-it-works.md` and the spec (`spec/gndctrl-spec-v0.1.0.md`) first. The
lock byte-format is implemented in three places that must stay in sync (they say so at
the top of each): `src/gndctrl/lockfile.py`, `hooks/atc-edit-gate.py`, and the
reference platform's harness gate. Hooks must remain single-file, stdlib-first
(PyYAML optional with graceful degradation), and fail-open on internal error — a hook
bug must never brick editing.
