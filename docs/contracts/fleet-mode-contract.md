# gndctrl Agent Contract — Fleet Mode

## What You Are

You are an AI agent operating inside a gndctrl-governed **fleet** — multiple projects
(airspaces) coordinated under a master `.gndctrl`. The codebase uses `@gndctrl:zone` and
`@gndctrl:node` markers to annotate zones and non-obvious functions. Read these markers
before acting — they tell you stability, dependencies, risk level, and which logbook
entries are relevant. They are the authority.

Your session memory is ephemeral. The gndctrl documents are permanent. Write important
decisions to the project `decision_log`, non-obvious solutions to `known_solutions`, and
create logbook entries for any `@gndctrl:node` markers you place. Any agent that works on
this project after you reads the same documents and picks up exactly where you left off.

> **Paths:** this template uses repo-relative paths (`.gndctrl`, `/logbook/`). Deployments
> may pin absolute paths — e.g. the pChisel reference deployment uses `/workspace/*.gndctrl`
> and `/workspace/logbook/`, and serves the master at `GET /api/pchisel/master`. The adapter
> substitutes these at install time.

---

## gndctrl Pre-flight — Run This Before Every Session

**Step 1 — Load master document** (~500 tokens)
Read the master `.gndctrl` (or fetch it from the deployment's master endpoint).
Load: platform conventions, fleet-wide tool registry, and the fleet airspace map.
Identify which airspaces the task touches.

**Step 2 — Load project document** (~500 tokens)
Read the project `.gndctrl` — architecture overview and the zone registry (index + briefs only).
If no `.gndctrl` exists, treat all code as `stability=active` and recommend `gndctrl init`
before the session ends.

**Step 3 — Resolve dependency graph**
- Identify which zones the task touches from the zone registry
- For each zone, read its `deps[]` list
- For any **cross-airspace dep** (`AIRSPACE://ZONE_ID`): load that airspace's `.gndctrl` first,
  then resolve the zone there
- If any dep has `stability=sensitive` or `stability=locked`: load that zone's full doc section
- Load relevant logbook entries from `/logbook/` by CRID (cold memory — only what's needed)

**Step 4 — Validate your weight class**
- Your weight class is declared at session start (ultralight → light → medium → heavy → super)
- For each task-relevant zone, check `minimum_agent_class`
- If your class is below the zone's minimum: **do not proceed.** State which zone, what class
  is required, and hold for a heavier agent or human override.

**Step 5 — Check zone locks**
- Read the fleet lock table in `.gndctrl.locks` at the fleet root
- Confirm no task-relevant zone — including cross-airspace deps — is locked by another
  active agent session. If locked: wait or reroute. Never enter a locked-by-another-agent zone.

**Step 6 — Issue clearance brief**
Confirm to the user:
- Your weight class and which zones you are cleared to enter (with airspace IDs)
- Any zones you are denied (state required class)
- Active stability constraints for this session
- Relevant logbook CRIDs you loaded
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

**Cross-zone changes:** If your task touches a zone you did not pre-flight, stop and tell
the user which zone is affected before proceeding.

**Cross-airspace writes:** You may never write to another airspace's `locked` or `sensitive`
zone without explicit cross-airspace clearance from the owning airspace. No exceptions.

---

## Working with @gndctrl:node Markers

When you encounter a `@gndctrl:node` marker:
- Read the `risk=` level before modifying the function
- Check `touches=[]` — if you are adding new system touches, flag it to the user
- Do not change a function's external signature without reading all zones that depend on it
- If a `crid=` is present, load the corresponding logbook entry from `/logbook/`

When you implement a workaround, write a non-obvious function, or take a calculated risk:
- Place a `@gndctrl:node` marker on the function
- Generate a CRID: `AIRSPACE-ZONE_ABBREV-YYYYMMDD-SEQ` (e.g. `CHI-AUTH-20260324-001`)
- Create the logbook entry at `/logbook/CRID-brief-description.md` **before the task is complete**

## Logbook Entry Format

```markdown
# Short Title
**CRID:** AIRSPACE-ZONE_ABBREV-YYYYMMDD-SEQ
**Airspace:** AIRSPACE (Project Name)
**Zone:** AIRSPACE://ZONE_ID
**Node:** AIRSPACE://ZONE_ID.function_name
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

## Writing to gndctrl Documents

Project and master documents are cache-stable by design. When you update one:
- **Append, never re-sort.** New `decision_log` and `known_solutions` entries go at the end of their section.
- **Volatile content stays at the bottom** — `open_questions` and `last_updated` only.
- **Never write runtime state** (locks, session info) into any document. That belongs in `.gndctrl.locks`.
- **Never modify the master document.** Project-level agents treat it as read-only; promotions
  go through the gndctrl Writer queue.
- Preserve key order and indentation exactly as found.

## Contributing Knowledge

When you solve a recurring problem — something that would save the next agent time — append it
to the project's `known_solutions`. When it applies beyond this project, mark it
`promote_to_master: true`; the gndctrl Writer will queue it for human review.

```yaml
- pattern_id: KS-001
  problem: "Short description of the recurring problem"
  solution: |
    What works and how — be specific, include code if useful
  context: "When to apply — stack, framework, constraint"
  promote_to_master: false
```

---

## You Must NEVER

- Enter a zone requiring a higher weight class than your own
- Modify code in a `locked` zone without human clearance
- Write to another airspace's `locked` or `sensitive` zone without explicit cross-airspace clearance
- Add a dependency on a `deprecated` zone
- Introduce a library not in the tool registry without flagging it first
- Leave a `@gndctrl:zone START` marker without a matching `END` marker
- Place a `@gndctrl:node` with a `crid=` and finish the task without the matching logbook entry

---

## Audit

Run `gndctrl audit` at any time to verify:
- Zone START/END pairs are balanced
- Node IDs reference real zones and cross-airspace refs resolve
- CRIDs are well-formed and have matching logbook files
- No circular dependencies (cross-airspace circular deps are critical failures)
- No dependencies on deprecated zones

A clean audit is a green light to proceed.
