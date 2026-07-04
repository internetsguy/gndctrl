# gndctrl Agent Contract — Single Mode

## What You Are

You are an AI agent working on a codebase governed by **gndctrl** — Ground Control for your codebase.
Source files use `@gndctrl:zone` and `@gndctrl:node` markers to declare stability, dependencies,
and risk for every zone and function. Read these markers before acting. They are the authority.

Your session context is ephemeral. The project's `.gndctrl` file is permanent.
Write important decisions to the `decision_log`, non-obvious solutions to `known_solutions`,
and create logbook entries for any `@gndctrl:node` markers you place. Any agent that works on
this project after you reads the same document and continues exactly where you left off.
Context lives in the project, not in you.

---

## gndctrl Pre-flight

Run this exact sequence at the start of every session before doing anything else:

**Step 1 — Load zone index** (~200 tokens)
Run `gndctrl preflight` (or read the zone registry in `.gndctrl` if the CLI is not installed).
This lists all zones with stability levels and one-line briefs.

**Step 2 — Identify task zone**
Match the user's first message to the relevant zone(s) in the registry and locate the
`@gndctrl:zone` markers in the code. Note the stability level of each zone the task will touch.

**Step 3 — Pre-flight the specific zones**
Run: `gndctrl preflight --zones ZONE_ID [--agent-class <your-class>]`
This loads the full clearance brief: stability rules, gotchas, decisions, and dep chain.
If the zone declares a `minimum_agent_class` above your class: **do not proceed.** State the
required class and hold.

**Step 4 — Load deep context for sensitive/locked zones**
If any task zone has `stability=sensitive` or `stability=locked`:
- Read the zone's full section in `.gndctrl`
- Read the zone docs for everything in its `deps[]`
- Load relevant logbook entries from `/logbook/` by CRID (cold memory — only what's needed)

**Step 5 — Confirm**
Briefly confirm: project name, which zone(s) you're entering, any gotchas to watch for,
and green light — or block with reason.

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

**No `.gndctrl` file found:** Treat all code as `stability=active`. Recommend running
`gndctrl init` and defining zones before the session ends.

**Parallel sessions:** If a `.gndctrl.locks` file exists, check it before entering a zone.
If another active session holds the lock on your task zone, wait or reroute — do not conflict.

---

## Working with @gndctrl:node Markers

When you encounter a node marker:

```python
# @gndctrl:node id=AUTH_CORE.verify_token | risk=high | touches=[SESSION, AUDIT_LOG] | crid=AUTH-20260324-001
```

1. Read `risk=` — if `high` or `critical`, load the zone's gotchas and decisions before editing
2. Check `touches=[]` — each zone listed is also affected by changes here; pre-flight them.
   If your change adds new system touches, flag it to the user.
3. If `crid=` is present, read the matching logbook entry from `/logbook/`
4. Do not change a function's external signature without reading all zones that depend on it

## Writing Node Markers

When you implement a workaround, write a non-obvious function, or take a calculated risk:

1. Place a `@gndctrl:node` marker on the line above the function:
   `# @gndctrl:node id=ZONE_ID.function_name | risk=<level> | crid=<CRID>`
2. Generate a CRID: `ZONE_ABBREV-YYYYMMDD-SEQ` (e.g. `AUTH-20260324-001`)
3. Create the logbook entry at `/logbook/CRID-brief-description.md` **before the task is complete**

Use `risk=high` if the function:
- handles auth, sessions, or permissions
- writes to persistent storage
- calls external APIs or services
- is on a critical execution path

Use `touches=[OTHER_ZONE]` if side effects cross zone boundaries.

---

## Logbook Entry Format

```markdown
# Short Title
**CRID:** ZONE_ABBREV-YYYYMMDD-SEQ
**Zone:** ZONE_ID
**Node:** ZONE_ID.function_name
**Stability:** [stability tier]
**Created:** YYYY-MM-DD
**Last updated:** YYYY-MM-DD
**Status:** unreviewed

## Changelog
| Date | Author | Change |
|---|---|---|
| YYYY-MM-DD | [your name] | Initial documentation |

## What this does
## Why it exists (the non-obvious part)
## What breaks if you change it
## Safe modification path
```

---

## Writing to the .gndctrl Document

The document is cache-stable by design. When you update it:
- **Append, never re-sort.** New `decision_log` and `known_solutions` entries go at the end of their section.
- **Volatile content stays at the bottom** — `open_questions` and `last_updated` only.
- **Never write runtime state** (locks, session info) into the document. That belongs in `.gndctrl.locks`.
- Preserve key order and indentation exactly as found.

When you solve a recurring problem, append it to `known_solutions`:

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

A clean audit is a green light to merge.
