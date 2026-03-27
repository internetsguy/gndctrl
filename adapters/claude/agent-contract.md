## What You Are

You are an AI agent operating inside a gndctrl-governed project.

The codebase uses `@gndctrl:zone` and `@gndctrl:node` markers to annotate zones and
non-obvious functions. Read these markers before acting — they tell you stability,
dependencies, risk level, and which logbook entries are relevant.

Your session memory is ephemeral. The gndctrl project document at `/workspace/*.gndctrl`
is permanent. Write important decisions to the decision_log, non-obvious solutions to
known_solutions, and create logbook entries for any @gndctrl:node markers you place.
Any agent that works on this project after you reads the same document and picks up
exactly where you left off.

---

## gndctrl Pre-flight — Run This Before Every Session

**Step 1 — Load zone index** (~200 tokens)
```bash
gndctrl preflight
```
This lists all zones with stability levels and descriptions.

**Step 2 — Load project document** (~500 tokens)
```bash
cat .gndctrl   # or run: gndctrl zones
```
If no `.gndctrl` file exists, treat all code as `stability=active`. Recommend running `gndctrl init` before the session ends.

**Step 3 — Resolve dependency graph**
- Identify which zones the task touches from the zone registry
- For each zone, read its `deps[]` list
- If any dep has `stability=sensitive` or `stability=locked`: load that zone's full doc section
- Load relevant logbook entries from `/workspace/logbook/` by CRID (cold memory — only what's needed)

**Step 4 — Validate your weight class**
- Your weight class maps to your model tier (ultralight → light → medium → heavy → super)
- For each task-relevant zone, check `minimum_agent_class`
- If your class is below the zone's minimum: **do not proceed**. State which zone, what class is required, and hold for a heavier agent or human override.

**Step 5 — Check zone locks**
- If another agent session is active on this project, confirm it is not currently working in the same zone
- In fleet mode: check cross-airspace zone locks before touching any cross-airspace dep

**Step 6 — Issue clearance brief**
Confirm to the user:
- Your weight class and which zones you are cleared to enter
- Any zones you are denied (state required class)
- Active stability constraints for this session
- Relevant logbook CRIDs you loaded
- Green light — or block with reason

Total pre-flight budget: **under 4,000 tokens.**

---

## gndctrl Guardrail Rules

| Stability | Before acting | Restriction |
|---|---|---|
| `locked` (5) | Surface proposed change as diff only. Do not implement. | Requires human confirmation before any action. |
| `sensitive` (4) | Read full zone doc + all dep zone docs. Surface risk summary. | Denied if agent weight class is below `minimum_agent_class`. |
| `stable` (3) | Read zone doc before structural changes. | Flag cross-zone edits to user before proceeding. |
| `active` (2) | Verify deps not broken. | No cross-zone restrictions. |
| `experimental` (1) | Act freely. | — |
| `deprecated` (0) | Refuse new dependencies. | Suggest migration path instead. |

**Cross-zone changes:** If your task touches a zone you did not pre-flight, stop and tell the user which zone is affected before proceeding.

---

## Working with @gndctrl:node Markers

When you encounter a `@gndctrl:node` marker:
- Read the `risk=` level before modifying the function
- Check `touches=[]` — if you are adding new system touches, flag it to the user
- Do not change a function's external signature without reading all zones that depend on it
- Load the corresponding logbook entry from `/workspace/logbook/` using the `crid=` field

When you implement a workaround, write a non-obvious function, or take a calculated risk:
- Place a `@gndctrl:node` marker on the function
- Generate a new CRID: `AIRSPACE-ZONE_ABBREV-YYYYMMDD-SEQ` (fleet mode) or `ZONE_ABBREV-YYYYMMDD-SEQ` (single mode)
- Create the corresponding logbook entry in `/workspace/logbook/CRID-description.md` **before** the task is complete

Logbook entry format:
```markdown
# Short Title
**CRID:** [your CRID]
**Airspace:** [airspace if fleet mode]
**Zone:** [zone id]
**Node:** [node id]
**Stability:** [stability tier]
**Created:** [date]
**Last updated:** [date]
**Status:** unreviewed

## Changelog
| Date | Author | Change |
|---|---|---|
| [date] | [your name] | Initial documentation |

## What this does
## Why it exists (the non-obvious part)
## What breaks if you change it
## Safe modification path
```

---

## Contributing Knowledge

When you solve a recurring problem — something that would save the next agent time — append it to the project's `known_solutions` section in the `.gndctrl` file.

When it's platform-wide (applies beyond this project), mark it as a candidate for master promotion by adding `promote_to_master: true`. The gndctrl Writer will queue it for human review.

Format:
```yaml
- pattern_id: KS-001
  problem: "Short description of the recurring problem"
  solution: |
    What works and how — be specific, include code if useful
  context: "When to apply — stack, framework, constraint"
  promote_to_master: false
```
