## What You Are

You are an AI agent working on a codebase governed by **gndctrl** — Ground Control for your codebase.
Source files use `@gndctrl:zone` and `@gndctrl:node` markers to declare stability, dependencies,
and risk for every zone and function. Read these markers before acting. They are the authority.

Your session context is ephemeral. The project's `.gndctrl` file is permanent.
Write important decisions and zone context there — not to your session memory.
Any agent that works on this project after you will read the same document and continue
exactly where you left off. Context lives in the project, not in you.

---

## gndctrl Pre-flight

Run this exact sequence at the start of every session before doing anything else:

**Step 1 — Load zone index** (~200 tokens)
Run: `gndctrl preflight`
This lists all zones with stability levels and descriptions.

**Step 2 — Identify task zone**
Read the user's first message and locate the relevant `@gndctrl:zone` markers in the code.
Find which zone(s) the task touches.

**Step 3 — Pre-flight the specific zones**
Run: `gndctrl preflight ZONE_ID --agent-class <your-class>`
This loads the full clearance brief: stability rules, gotchas, decisions, and dep chain.

**Step 4 — Load extra context for sensitive/locked zones**
If the task zone has stability=sensitive or stability=locked:
- Read the zone's full section in the project documentation
- Read documentation for all declared dependency zones

**Step 5 — Confirm**
Briefly confirm: project name, which zone(s) you're entering, any gotchas to watch for.
Total pre-flight budget: under 4,000 tokens.

---

## Stability Rules

These rules are mandatory. They are part of the gndctrl governance contract.

| Stability | Before acting | Restriction |
|---|---|---|
| locked | Surface proposed change as a diff. Do not implement. | Wait for human confirmation. |
| sensitive | Read full zone doc + all dep zone docs. Surface risk summary. | — |
| stable | Read zone doc before structural changes. | Flag cross-zone edits to user. |
| active | Verify deps not broken. | No cross-zone restrictions. |
| experimental | Act freely. | — |
| deprecated | Refuse new dependencies. | Suggest migration path instead. |

**Cross-zone changes:** If your task touches a zone other than the one you pre-flighted,
stop and tell the user which other zone is affected before proceeding.

**No .gndctrl file found:** Treat all code as stability=active. Recommend running
`gndctrl init` and defining zones before the session ends.

---

## Node Markers — Before You Touch a Function

When you encounter a node marker in the code:

```python
# @gndctrl:node id=AUTH_CORE.verify_token | risk=high | touches=[SESSION, AUDIT_LOG]
```

You must:
1. Check `risk` — if `high` or `critical`, load the zone's gotchas and decisions before editing
2. Check `touches` — each zone listed is also affected by changes here; pre-flight them
3. Check `crid` if present — this function was changed under a control record; read the logbook entry

---

## Writing Node Markers

When you add or modify a function in a governed zone, add a node marker on the line above:

```python
# @gndctrl:node id=ZONE_ID.function_name | risk=low
```

Use `risk=high` if the function:
- handles auth, sessions, or permissions
- writes to persistent storage
- calls external APIs or services
- is on a critical execution path

Use `touches=[OTHER_ZONE]` if side effects cross zone boundaries.

---

## Logbook — Recording Significant Changes

For any change to a `sensitive` or `locked` zone, create a logbook entry:

1. Generate a CRID: `ZONE-YYYYMMDD-NNN` (e.g. `AUTH-20260324-001`)
2. Create the file: `logbook/AUTH-20260324-001-brief-description.md`
3. Add `crid=AUTH-20260324-001` to the node marker for the changed function

Logbook entry format:

```markdown
# AUTH-20260324-001 — Brief description of what changed

**Zone:** AUTH_CORE
**Date:** 2026-03-24
**Risk:** high

## What changed
[1-3 sentences describing the change]

## Why
[The business or technical reason]

## Gotchas introduced
[Any new edge cases or constraints the next agent should know]
```

---

## Audit

Run `gndctrl audit` at any time to check:
- Zone START/END pairs are balanced
- Node IDs reference real zones
- CRIDs have matching logbook files
- No circular dependencies
- No dependencies on deprecated zones

A clean audit is a green light to merge.
