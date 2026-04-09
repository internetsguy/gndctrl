## What You Are

You are an AI agent operating inside a gndctrl-governed project.

The codebase uses `@gndctrl:zone` and `@gndctrl:node` markers to annotate zones and
non-obvious functions. Read these markers before acting — they tell you stability,
dependencies, risk level, and which logbook entries are relevant.

Your session memory is ephemeral. The gndctrl project document at `.gndctrl`
is permanent. Write important decisions to the decision_log, non-obvious solutions to
known_solutions, and create logbook entries for any `@gndctrl:node` markers you place.
Any agent that works on this project after you reads the same document and picks up
exactly where you left off.

---

## gndctrl Pre-flight — Run This Before Every Session

At the start of every session, before doing anything else:

**Step 1 — Load zone index**
Read the `.gndctrl` file in the project root (or run `gndctrl preflight` if the CLI is installed).
This gives you all zones with stability levels and descriptions.

**Step 2 — Identify task zone**
Match the user's first message to the relevant zone(s) in the registry.
Note the stability level of each zone the task will touch.

**Step 3 — Load deep context for sensitive/locked zones**
If any task zone has `stability=sensitive` or `stability=locked`:
- Read the zone's full section in the project document
- Read all zone docs listed in its `deps[]`
- Load relevant logbook entries from `/logbook/` by CRID

**Step 4 — Validate your weight class**
Your weight class maps to your model tier (ultralight → light → medium → heavy → super).
Check `minimum_agent_class` for each task-relevant zone.
If your class is below the zone's minimum: **do not proceed**. State which zone requires a heavier agent.

**Step 5 — Issue clearance brief**
Confirm to the user:
- Your weight class and which zones you are cleared to enter
- Any zones you are denied and the required class
- Active stability constraints for this session
- Relevant logbook CRIDs loaded
- Green light — or block with reason

Total pre-flight budget: **under 4,000 tokens.**

---

## Stability Rules

These rules are mandatory. They are part of the gndctrl governance contract.

| Stability | Before acting | Restriction |
|---|---|---|
| `locked` (5) | Surface proposed change as diff only. Do not implement. | Requires human confirmation before any action. |
| `sensitive` (4) | Read full zone doc + all dep zone docs. Surface risk summary. | Denied if weight class is below `minimum_agent_class`. |
| `stable` (3) | Read zone doc before structural changes. | Flag cross-zone edits to user before proceeding. |
| `active` (2) | Verify deps not broken. | No cross-zone restrictions. |
| `experimental` (1) | Act freely. | — |
| `deprecated` (0) | Refuse new dependencies. | Suggest migration path instead. |

**Cross-zone changes:** If your task touches a zone you did not pre-flight,
stop and tell the user which zone is affected before proceeding.

**No `.gndctrl` file found:** Treat all code as `stability=active`. Recommend
running `gndctrl init` before the session ends.

---

## Working with @gndctrl:node Markers

When you encounter a `@gndctrl:node` marker:
- Read the `risk=` level before modifying the function
- Check `touches=[]` — if you are adding new system touches, flag it to the user
- Do not change a function's external signature without reading all zones that depend on it
- If a `crid=` is present, load the corresponding logbook entry from `/logbook/`

When you implement a workaround, write a non-obvious function, or take a calculated risk:
- Place a `@gndctrl:node` marker on the function
- Generate a CRID: `ZONE-YYYYMMDD-NNN` (single mode) or `AIRSPACE-ZONE-YYYYMMDD-NNN` (fleet mode)
- Create the logbook entry in `/logbook/CRID-description.md` **before the task is complete**

Logbook entry format:
```markdown
# ZONE-YYYYMMDD-NNN — Brief description

**Zone:** ZONE_ID
**Date:** YYYY-MM-DD
**Risk:** low | medium | high

## What changed
## Why
## Gotchas introduced
## Safe modification path
```

---

## Contributing Knowledge

When you solve a recurring problem — something that would save the next agent time — append it to
`known_solutions` in the `.gndctrl` file.

When it applies beyond this project, mark it as `promote_to_master: true`.

```yaml
- pattern_id: KS-001
  problem: "Short description of the recurring problem"
  solution: |
    What works and how — be specific, include code if useful
  context: "When to apply — stack, framework, constraint"
  promote_to_master: false
```

---

## Audit

Run `gndctrl audit` at any time to verify:
- Zone START/END pairs are balanced
- Node IDs reference real zones
- CRIDs have matching logbook files
- No circular dependencies
- No dependencies on deprecated zones

A clean audit is a green light to proceed.
