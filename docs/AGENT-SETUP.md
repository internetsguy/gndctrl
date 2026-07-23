# gndctrl — Agent Setup Runbook

**Audience:** an AI agent instructed to install gndctrl into a project.
**Rule zero:** a step is complete when its VERIFY command produces the expected result —
never before, and never on the strength of your own summary. If a VERIFY fails, stop and
report it to the user; do not improvise around it, and do not proceed to later phases.

Two hard prohibitions for the whole runbook:
- Never lower a zone's stability, delete a zone, or edit a hazard to make a check pass.
- Never mark the final report complete if any live-fire test (Phase 6) was skipped —
  say explicitly which tests ran and which didn't.

---

## Phase 0 — Preconditions

- [ ] `python3 --version` → 3.9+
- [ ] `python3 -m pip --version` → exits 0
- [ ] Determine the runtime: is this Claude Code? The ATC hooks (edit gate, ops gate,
      session-start) are Claude Code `PreToolUse`/`SessionStart` hooks. On any other
      agent runtime, Phases 1's hook steps don't apply — install the CLI only, apply the
      agent contract from `docs/contracts/`, and tell the user enforcement is
      contract-governed (honor system) until a commit-time gate or harness gate exists.

## Phase 1 — Install the CLI + hooks

- [ ] Run `./install.sh` from the repo root (or the curl one-liner from the README).
- [ ] VERIFY CLI: `gndctrl --version` → prints a version, exits 0.
- [ ] VERIFY hooks on disk: `ls ~/.claude/hooks/atc-edit-gate.py ~/.claude/hooks/atc-ops-gate.py ~/.claude/hooks/atc-session-start.py` → all three exist.
- [ ] VERIFY wiring: `python3 -c "import json;c=json.load(open('$HOME/.claude/settings.json'));h=json.dumps(c.get('hooks',{}));print(all(x in h for x in ['atc-edit-gate','atc-ops-gate','atc-session-start']))"` → `True`.
- [ ] VERIFY zone-level enforcement is possible: `python3 -c "import yaml; print('ok')"` →
      `ok`. If PyYAML is missing the edit gate silently degrades to doc-read-only gating;
      install it (`pip install pyyaml`) or report the degradation to the user explicitly.
- [ ] VERIFY hazard registry exists: `ls ~/.claude/atc-ops-hazards.json` → exists
      (seeded sample is fine at this stage; Phase 5 makes it real).

## Phase 2 — Initialize the project

- [ ] From the project root: `gndctrl init`
- [ ] VERIFY: a `<project>.gndctrl` (or `.gndctrl`) exists at the root and `logbook/` exists.

## Phase 3 — Write the real zone map (the step that matters most)

The init template ships a placeholder `EXAMPLE_ZONE`. **A project whose registry still
contains EXAMPLE_ZONE is not governed** — the gates will technically fire, but they'll
be enforcing a map of nothing. This phase is the actual work.

- [ ] Read `spec/example-real-world.gndctrl` first — it shows the target shape: gotchas
      written as numbered invariants, decisions with CRIDs, per-path comments, every tier
      earning its place.
- [ ] Study the codebase and draft zones. Minimum bar for each zone: `stability`,
      `paths`, and a one-line `description` that says why the tier was chosen.
- [ ] Tier assignment guidance — look for the project's analogues of:
      `sensitive` → auth, billing/payments, session handling, crypto, permission checks;
      `locked` → legal documents, compliance text, anything where every change is a
      business decision (add `minimum_agent_class: super`);
      `stable` → migration chains, public API contracts, data schemas;
      `active` → the main feature surface; `experimental` → scratch/spike code;
      `deprecated` → code awaiting removal (name the migration path in the description).
- [ ] Ask the user to confirm the draft before finalizing. Zone tiers are their risk
      decisions, not yours — present the map, take corrections.
- [ ] Coverage check: every path a task is likely to touch should match some zone.
      `git ls-files | head -50` against your `paths[]` patterns; important uncovered
      areas mean missing zones, not a smaller map.
- [ ] VERIFY no placeholder: `grep -c EXAMPLE_ZONE *.gndctrl` → `0`.
- [ ] VERIFY registry is live: `gndctrl zones` → lists your real zones with tiers.
- [ ] VERIFY integrity: `gndctrl audit` → exits 0. If it exits 1, fix the reported
      violations; do not proceed with a failing audit.

## Phase 4 — Inline markers and logbook (as needed)

- [ ] Add `@gndctrl:zone START/END` markers ONLY where a single file spans more than one
      zone — path-based zones need no inline markers.
- [ ] Add `@gndctrl:node` markers to individually risky functions (external side effects,
      non-obvious invariants), each with a `crid=` and a matching file in `logbook/`.
- [ ] VERIFY: `gndctrl audit` → still exits 0 (A1 pair matching, A3 CRID↔logbook links).

## Phase 5 — Ops hazards (platform-specific dangerous commands)

- [ ] With the user, list commands that can take their platform down or destroy state
      (service restarts, DNS reloads, container recreates, destructive migrations).
      Write each into `~/.claude/atc-ops-hazards.json` with a `pattern` targeting the RAW
      dangerous command, a `doc` pointing at the governing document, and a `reason`
      naming the blast radius.
- [ ] Consider investigation tripwires (`severity: info`, pattern = a zone's directory
      path) for zones whose documented gotchas agents keep re-deriving — see
      hooks/README.md.
- [ ] If the user has no such commands, delete the sample entries and record "no ops
      hazards — confirmed with user" in your report. An unreviewed sample registry is
      not a decision.
- [ ] VERIFY: `python3 -c "import json;print(len(json.load(open('$HOME/.claude/atc-ops-hazards.json'))['hazards']))"` → parses, prints the agreed count.

## Phase 6 — Live-fire self test (requires a NEW session)

Hooks load at session start. The session that ran the installer is NOT protected by the
hooks it just installed — tell the user setup is staged and the test needs a fresh
session. In the new session:

- [ ] T-A (session hook): the session opens with a gndctrl pre-flight context block
      listing the governed project. If absent → session hook not wired; return to Phase 1.
- [ ] T-B (doc-read deny): WITHOUT reading the .gndctrl, attempt a trivial edit to a
      governed file (add a comment). EXPECTED: denied with the read-first message. If the
      edit goes through → the edit gate is not live; stop and report.
- [ ] T-C (clear and retry): Read the governing .gndctrl (the relevant zone section),
      retry the same edit. EXPECTED: allowed. Then revert the comment.
- [ ] T-D (locked zone), only if a locked zone exists: attempt an edit to a locked-zone
      file AFTER having read the doc. EXPECTED: denied with the human-clearance message.
      Do NOT retry and do NOT touch the zone's stability; the deny IS the pass result.
- [ ] T-E (ops gate), only if Phase 5 defined hazards: construct a matching command in
      its HARMLESS form if one exists (e.g. a `--dry-run` variant that still matches the
      pattern); EXPECTED: denied until the hazard's doc is read. If no harmless form
      matches, skip and mark T-E "not testable safely" — never run a live dangerous
      command to test a gate.

## Phase 7 — Report to the user

Deliver a short report containing, at minimum:
1. The zone map: every zone, tier, and one-line rationale.
2. Checklist state: every VERIFY above with its actual observed result, including any
   marked degraded/skipped/not-testable, with reasons.
3. What is NOT enforced on this install (be explicit; this list is honest, not
   optional): Bash-mediated file writes bypass the edit gate; no commit-time gate;
   non-Claude agents are contract-governed only; per-zone read tracking is per-doc,
   not per-zone.
4. The standing rules the user should know: locked zones need them, not you; one agent
   per zone; `GNDCTRL_AGENT_CLASS` opt-in for class floors.

Setup is complete when the user has seen this report — not when the files exist.
