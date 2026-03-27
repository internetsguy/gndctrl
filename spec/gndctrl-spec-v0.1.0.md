# gndctrl — Project Specification
**Version:** 0.1.0-draft
**Date:** 2026-03-23
**Status:** Private / Pre-release
**Author:** Adam Harnden

---

## The Problem

Every AI coding agent starts blind. It doesn't know which parts of your codebase are stable, which are critical, which are actively being refactored, or which should never be touched without human review. Without that awareness, agents cause damage — not out of incompetence, but because the codebase has no way to communicate its own structure and risk levels to them.

Existing tools try to solve this with documentation injection (Agent OS) or agent identity definitions (GitAgent). Neither solution addresses the real gap: **the codebase itself has no voice.**

This is true whether you're a solo developer with one repository or a platform team running twenty containerised projects in parallel. The problem scales with complexity — and so does gndctrl.

---

## What gndctrl Is

gndctrl is a **zone-based governance and enforcement layer for AI agents operating in codebases.**

It gives your codebase a voice by annotating source files directly with zone markers that any agent, CI system, or tool can read. It then enforces those annotations at runtime — blocking agents from touching locked zones, preventing two agents from conflicting in the same zone simultaneously, and requiring human clearance before sensitive areas are modified.

Think of it as **Air Traffic Control for your codebase.**

In real aviation, the same ATC principles govern a single regional airport and the entire national airspace system. Ground rules, zone classifications, clearance protocols — the mental model is identical whether you're managing one runway or hundreds of flight paths. Only the scale changes.

gndctrl works the same way. A solo developer adds it to a single project and it works immediately. A platform team running a multi-project dev environment gets the same system — just bigger airspace, with a master controller above each project.

---

## Scale Modes

gndctrl operates in two modes. The terminology, marker syntax, and enforcement rules are identical in both. Scale is a configuration choice, not a conceptual shift.

### Single Mode

One `.gndctrl` file at the project root. Zones are local to that project. No master, no fleet, no additional complexity. The right starting point for any new project.

```
my-project/
├── .gndctrl          ← single source of truth
├── logbook/          ← logbook entries for this project
└── src/
```

> **File naming:** `.gndctrl` may also be written as a named file (e.g., `my-project.gndctrl`, `master.gndctrl`) rather than a hidden dot-file. Named files are preferred when multiple `.gndctrl` documents coexist in the same directory (e.g., project file + master reference). The spec is indifferent to the naming convention — tooling resolves by `gndctrl_spec` field and `airspace` declaration, not by filename.

### Fleet Mode

A master `.gndctrl` at the platform level governs multiple projects. Each project has its own `.gndctrl` and its own **airspace ID** — a short code that namespaces its zones across the fleet.

```
platform/                        ← fleet root
├── .gndctrl                     ← master: platform conventions, tool registry, fleet airspace map
├── chisel-app/
│   ├── .gndctrl                 ← airspace: CHI
│   └── logbook/
├── payment-service/
│   ├── .gndctrl                 ← airspace: PMT
│   └── logbook/
└── auth-service/
    ├── .gndctrl                 ← airspace: AUTH
    └── logbook/
```

This maps directly onto real ATC hierarchy:

| ATC Layer | Governs | gndctrl equivalent |
|---|---|---|
| Ground Control | One airport's tarmac | Single mode — local zones |
| Tower | One airport's airspace | Single project with external deps |
| TRACON | Multiple airports in a region | Fleet mode — dev environment like Chisel |
| Center (ARTCC) | En-route across a whole country | Enterprise / SaaS platform |

A developer who learns gndctrl on their personal project already knows how to operate in a fleet environment. The same mental model, bigger airspace.

---

## Core Concepts

### Airspace IDs

In fleet mode, every project is assigned a short airspace ID — typically 3–4 characters, similar to an ICAO airport code. The airspace ID namespaces all zones and logbook entries belonging to that project.

```
CHI     ← Chisel platform
PMT     ← Payment service
AUTH    ← Auth service
DSN     ← Design system
```

In single mode, the airspace ID is optional. In fleet mode it is required and must be declared in the project `.gndctrl`.

Zones are referenced with their airspace prefix when crossing project boundaries:

```
AUTH_CORE              ← local reference within the same airspace
CHI://AUTH_CORE        ← cross-airspace reference from another project
PMT://STRIPE_SYNC      ← cross-airspace reference to payment service
```

### Agent Weight Classes

Every agent operating under gndctrl is assigned a **weight class** — borrowed directly from aviation's aircraft weight classification system. Weight class determines which zones an agent is cleared to enter. A zone can require a minimum weight class, ensuring that only sufficiently capable agents are trusted with critical or sensitive work.

| Weight Class | Aviation Reference | Agent Type | Current Providers |
|---|---|---|---|
| **Super** | A380, An-225 — largest commercial aircraft | Frontier reasoning models. Reserved for `locked` zones and the most critical architectural decisions. | Claude Opus |
| **Heavy** | 747, 777 — wide-body long-haul | Large capable models. Standard for `sensitive` zones, complex planning, security review. | Claude Sonnet, OpenAI GPT-4o |
| **Medium** | 737, A320 — narrow-body workhorses | Mid-size models. Good for code generation, UI work, standard active-zone tasks. | Gemini, OpenAI Codex CLI |
| **Light** | Cessna 172 — small general aviation | Small/fast models. Summaries, markdown updates, simple checks on `experimental` zones. | Small local models (3B) |
| **Ultralight** | Drone / glider — no pilot required | Scripted or rule-based agents. Audits, linting, file watching. No LLM required. | gndctrl Auditor, gndctrl Writer |

Weight class is a **minimum floor, not a ceiling.** A heavier agent is always cleared to enter a lighter zone — a Super agent can go anywhere, a Heavy agent can enter any Medium, Light, or Ultralight zone freely. Clearance is only denied when an agent's class falls *below* the zone's minimum. A Light agent cannot enter a Heavy zone. A Medium cannot enter a Super zone.

Weight class is declared per agent session and checked at pre-flight. A Medium agent attempting to enter a Heavy-required zone is denied clearance — not blocked arbitrarily, but told exactly why and what class is required.

**Current provider lineup (Phase 1):**
- Claude Opus → Super
- Claude Sonnet → Heavy
- OpenAI GPT-4o → Heavy
- Gemini → Medium
- OpenAI Codex CLI → Medium (schema/migrations, structured code tasks)

Multi-agent zone routing follows weight class rules: when a zone requires Heavy and only a Medium agent is available, the scheduler holds the task until a Heavy agent is free — or escalates to human to decide whether to override.

### Zone Types

gndctrl recognises five zone types. Each has its own pre-flight contract template, so agents only load what is relevant to their task. Zone types apply equally in single and fleet mode.

| Type | Covers |
|---|---|
| `code` | Default — logic, functions, APIs |
| `design` | UI components, tokens, style rules, design language |
| `data` | Schemas, migrations, models |
| `config` | Environment, infrastructure, secrets |
| `docs` | Documentation, changelogs, specs |

### Three-Layer Marking System

Zone coverage works at three levels, from broad to surgical. The same three layers apply in single and fleet mode.

**Layer 1 — Directory level** (`.gndctrl` file, path patterns)
The source of truth. Zones defined by file path patterns. Any file matching a pattern automatically inherits the zone. New files added to the feature are captured automatically.

Single mode example:
```yaml
airspace: null        # omit or null in single mode
version: "0.1.0"

zones:
  PAYMENT:
    stability: sensitive
    type: [code, data]
    paths:
      - "src/components/Payment*"
      - "src/hooks/usePayment*"
      - "src/api/payment*"
  DESIGN_SYSTEM:
    stability: stable
    type: [design]
    paths:
      - "src/styles/*"
      - "src/tokens/*"
      - "src/components/ui/*"
```

Fleet mode example (payment service):
```yaml
airspace: PMT
version: "0.1.0"
master_ref: "../.gndctrl"

zones:
  STRIPE_SYNC:
    stability: sensitive
    type: [code, data]
    deps: [AUTH://AUTH_CORE, PMT://WEBHOOK_HANDLER]
    minimum_agent_class: heavy
    paths:
      - "src/billing/stripe*"
      - "src/billing/webhook*"
  WEBHOOK_HANDLER:
    stability: stable
    type: [code]
    deps: [AUTH://AUTH_CORE]
    minimum_agent_class: medium
    paths:
      - "src/webhooks/*"
```

**Layer 2 — File level** (inline `@gndctrl:zone` marker)
Used when a file belongs to a zone the path pattern would not catch, or when a single file spans multiple zones.

```python
# @gndctrl:zone START | id=PMT://STRIPE_SYNC | deps=[AUTH://AUTH_CORE] | stability=sensitive | type=code
# @gndctrl:zone meta | owner=adam | doc=.gndctrl#zones/stripe-sync
```

Every zone has an explicit closing marker. The Auditor flags unclosed zones as integrity errors.

```python
# @gndctrl:zone END | id=PMT://STRIPE_SYNC
```

In single mode, the airspace prefix is omitted:
```python
# @gndctrl:zone START | id=STRIPE_SYNC | deps=[AUTH_CORE] | stability=sensitive | type=code
```

**Layer 3 — Function level** (inline `@gndctrl:node` marker)
The most granular layer. Agents place these when they encounter or create something non-obvious — a workaround, a fragile dependency, a gotcha, a performance edge case. Placing a node marker requires creating a corresponding logbook entry.

```python
# @gndctrl:node id=PMT://STRIPE_SYNC.reconcile_payment | risk=high | touches=[ledger, webhook_queue, stripe_api] | crid=PMT-20260323-001
# @gndctrl:node note="Not idempotent. Caller must acquire distributed lock before invoking."
async def reconcile_payment(event: dict) -> bool:
    ...
```

Multi-language examples:

```typescript
// @gndctrl:zone START | id=AUTH://AUTH_CORE | deps=[] | stability=stable | type=code
// @gndctrl:node id=AUTH://AUTH_CORE.verifyToken | risk=high | touches=[jwt_store] | crid=AUTH-20260323-001
export async function verifyToken(token: string): Promise<User> { ... }
// @gndctrl:zone END | id=AUTH://AUTH_CORE
```

```css
/* @gndctrl:zone START | id=DSN://DESIGN_SYSTEM | deps=[] | stability=stable | type=design */
/* @gndctrl:node id=DSN://DESIGN_SYSTEM.colorTokens | risk=medium | touches=[theme_provider] | crid=DSN-20260323-001 */
```

```go
// @gndctrl:zone START | id=CHI://DATA_PIPELINE | deps=[AUTH://AUTH_CORE] | stability=active | type=data
// @gndctrl:node id=CHI://DATA_PIPELINE.ingestRecord | risk=medium | touches=[postgres, redis] | crid=CHI-20260323-001
func ingestRecord(ctx context.Context, record Record) error { ... }
// @gndctrl:zone END | id=CHI://DATA_PIPELINE
```

### Node Marker Field Reference

| Field | Required | Values | Description |
|---|---|---|---|
| `id` | Yes | `[AIRSPACE://]ZONE_ID.function_name` | Namespaced under parent zone. Airspace prefix required in fleet mode. |
| `risk` | Yes | `low`, `medium`, `high`, `critical` | Risk level for this specific function |
| `touches` | No | `[system, ...]` | External systems this function reaches |
| `note` | No | String | Short inline note for agent reference |
| `crid` | Yes (if non-obvious) | `[AIRSPACE-]ZONE-YYYYMMDD-SEQ` | Links this marker to its logbook entry |
| `minimum_agent_class` | No | `ultralight`, `light`, `medium`, `heavy`, `super` | Override zone-level class requirement for this specific function |

### The Logbook (`/logbook` directory)

When an agent places a `@gndctrl:node` marker on a non-obvious function, it must create a corresponding logbook entry in `/logbook`. This is the institutional memory layer — the timestamped, versioned record of fragile things, workarounds, and calculated risks.

Each project maintains its own `/logbook` in both single and fleet mode. In fleet mode the master `.gndctrl` can query across all project logbooks for fleet-wide pattern discovery.

#### Control Record ID (CRID)

Every logbook entry has a CRID that ties it permanently to its marker. The CRID is immutable — it never changes even as the entry is updated.

**Single mode format:** `[ZONE_ABBREV]-[YYYYMMDD]-[SEQ]`
**Fleet mode format:** `[AIRSPACE]-[ZONE_ABBREV]-[YYYYMMDD]-[SEQ]`

```
STR-20260323-001        ← single mode, STRIPE zone
PMT-STR-20260323-001    ← fleet mode, Payment airspace, STRIPE zone
AUTH-AUTH-20260323-001  ← fleet mode, Auth airspace, AUTH_CORE zone
CHI-DAT-20260323-001    ← fleet mode, Chisel airspace, DATA zone
```

The CRID is referenced in the node marker:
```python
# @gndctrl:node id=PMT://STRIPE_SYNC.reconcile_payment | risk=high | crid=PMT-STR-20260323-001
```

#### Logbook Directory Structure

```
logbook/
├── PMT-STR-20260323-001-stripe-retry-workaround.md
├── AUTH-AUTH-20260323-001-session-edge-case.md
└── CHI-DAT-20260323-001-pipeline-backpressure.md
```

Filenames are prefixed with the CRID for instant sortability and cross-airspace traceability.

#### Logbook Entry Format

```markdown
# Stripe Retry Workaround
**CRID:** PMT-STR-20260323-001
**Airspace:** PMT (Payment Service)
**Zone:** PMT://STRIPE_SYNC
**Node:** PMT://STRIPE_SYNC.reconcile_payment
**Stability:** sensitive
**Created:** 2026-03-23
**Last updated:** 2026-03-23
**Status:** unreviewed

## Changelog
| Date | Author | Change |
|---|---|---|
| 2026-03-23 | Claude | Initial documentation |

## What this does
## Why it exists (the non-obvious part)
## What breaks if you change it
## Safe modification path
```

Agents load relevant logbook entries during pre-flight for any zone they are touching. The Auditor validates that every CRID referenced in a node marker has a matching logbook entry — missing entries are flagged as integrity violations.

### Stability Tiers

Stability tiers apply identically in single and fleet mode. Cross-airspace dependencies inherit the stability rules of the zone they reference.

| Tier | Aviation Equivalent | Agent Behaviour |
|---|---|---|
| `deprecated` | Decommissioned airspace | Flag for removal, do not extend. No new deps may point here. |
| `experimental` | Uncontrolled (Class G) | Agents operate freely. No dep check required. |
| `active` | Controlled (Class E) | Normal development. Dep check required for cross-zone changes. |
| `stable` | Approach controlled (Class C/D) | Agent must read full zone doc before structural changes. |
| `sensitive` | Restricted | Agent must read full zone doc + all dep chain docs. Must surface risk summary before proceeding. |
| `locked` | Prohibited | Agent must not modify. Human clearance required. Agent surfaces proposed change for review only. |

**Stability override rules:**
- Zones may lower stability from master defaults (e.g. `stable` → `active` during active development)
- Zones may never raise a `locked` designation without explicit human approval
- Cross-airspace zones may never be overridden by a dependent project — only by the owning airspace
- All overrides must be logged in the decision log

### Zone Locking (Multi-Agent)

The scheduler enforces a zone lock table. When an agent enters a zone it acquires the lock. No second agent can touch that zone until the lock is released.

In fleet mode, the lock table is fleet-wide. An agent working in the `PMT` airspace that depends on `AUTH://AUTH_CORE` will see if another agent has that zone locked — and will wait or reroute rather than conflict. This is the core capability that makes true parallel multi-agent development safe.

### Hot Memory vs Cold Memory

gndctrl manages agent context in two tiers to keep token usage minimal. The same principle applies in both modes — fleet mode simply has an additional hot memory layer at the master level.

**Hot memory — always loaded at pre-flight**

Single mode:
- Project conventions and tool registry
- Project overview and architecture summary
- Zone index (map only, not full zone docs)

Fleet mode (additional):
- Master platform conventions and fleet-wide tool registry
- Fleet airspace map (which projects exist, their airspace IDs, their stability posture)
- Cross-airspace dependency summary for relevant zones

**Cold memory — loaded on demand**
- Full zone documentation
- Dep chain docs for sensitive/locked zones
- Logbook entries for relevant nodes (matched by CRID)
- Known solutions applicable to the task

A well-maintained gndctrl setup delivers full pre-flight context in under 4,000 tokens for most tasks — compared to 40,000–200,000+ for raw codebase loading. This holds in both single and fleet mode because cold memory is only loaded when the task actually requires it.

### Pre-flight Protocol

Before an agent begins any task, gndctrl runs a mandatory pre-flight sequence. Fleet mode adds Steps 1a and 3a; single mode skips them.

```
GNDCTRL PRE-FLIGHT
──────────────────
Step 1 [fleet only]: Load master .gndctrl
  → Read platform conventions and fleet-wide tool registry
  → Load fleet airspace map
  → Identify which airspaces the task touches

Step 2: Load project .gndctrl
  → Read project overview + architecture
  → Load zone index (full map, hot memory)
  → Identify task-relevant zones

Step 3: Resolve dependency graph
  → For each relevant zone, trace deps[]
  → For cross-airspace deps [fleet only]: load dep airspace .gndctrl and resolve zone there
  → Load full zone docs for sensitive/locked zones in dep chain (cold memory)
  → Load logbook entries for relevant nodes (matched by CRID)

Step 4: Validate agent weight class
  → Identify the requesting agent's weight class (Super / Heavy / Medium / Light / Ultralight)
  → For each relevant zone, check minimum_agent_class requirement
  → If agent class is insufficient: deny clearance for that zone, state required class
  → If agent class meets requirement: proceed

Step 5: Check zone lock table
  → Confirm no relevant zones are locked by another agent
  → In fleet mode: check lock table across all airspaces in dep chain

Step 6: Issue clearance brief
  → Agent weight class confirmed
  → Authorised zones for this session (with airspace IDs in fleet mode)
  → Any zones denied due to weight class — with required class stated
  → Active stability constraints
  → Locked/sensitive zones in dep chain
  → Relevant gotchas and logbook entry references
  → Green light to proceed — or block with reason
```

### Dependency Resolution

```
1. Parse task description → identify likely zones to be touched
2. For each identified zone:
   a. Load zone doc from project .gndctrl
   b. Read deps[] list
   c. For each dep:
      i.   If local: load zone doc from same .gndctrl
      ii.  If cross-airspace [fleet]: load dep airspace .gndctrl, then load zone doc
      iii. Check dep stability tier
      iv.  If sensitive or locked, add to required-reads
3. Agent reads all required-reads before receiving clearance
4. Agent proceeds within authorised zone scope
5. Any action that would modify an unauthorised zone → agent flags it, does not act
```

Circular dependencies between `sensitive` or `locked` zones trigger immediate escalation to human review. In fleet mode, circular cross-airspace dependencies are treated as critical integrity failures.

### Guardrail Enforcement

Guardrails operate at two levels in both modes:

**Level 1 — Agent-level (soft guardrail)**
The agent's system prompt includes gndctrl awareness instructions. The agent self-enforces by reading pre-flight output and flagging scope violations.

**Level 2 — Platform-level (hard guardrail)**
The platform enforces independently of agent judgment:
- **File watch rules** — files in `locked` zones cannot be written without an approval token in session context
- **Commit gating** — pre-commit hooks parse gndctrl markers and reject commits touching `locked` zones without an approval record
- **Session scoping** — agent container can be restricted to write access only within authorised zone directories
- **Fleet mode addition** — cross-airspace writes require the owning airspace to grant clearance; a foreign agent cannot write to another airspace's locked zone under any circumstances

**Violation report format:**
```
GNDCTRL GUARDRAIL TRIGGERED
Airspace: PMT (Payment Service)       ← omitted in single mode
Zone: PMT://STRIPE_SYNC (stability=sensitive)
Agent class: Medium
Required class: Heavy
Action attempted: Modify reconcile_payment signature
Resolution: Task held — awaiting Heavy class agent (Claude Sonnet) or human override
```

```
GNDCTRL GUARDRAIL TRIGGERED
Airspace: PMT (Payment Service)
Zone: PMT://STRIPE_SYNC (stability=sensitive)
Agent class: Heavy
Action attempted: Modify reconcile_payment signature
Required: Read STRIPE_SYNC and all dep zone docs first
Dep chain: [AUTH://AUTH_CORE, PMT://WEBHOOK_HANDLER]
Action: Loading dependency docs now. Re-evaluating.
```

### Agent Behavior Contract

gndctrl ships two agent contracts — one for each scale mode. Both share the same zone rules and stability enforcement; they differ in scope and overhead.

**Single-mode contract** — delivered to agents working inside individual projects. No weight class enforcement, no cross-airspace lookups. Pre-flight is a 5-step sequence: load master context → load project doc → identify task zone → load deps if sensitive/locked → confirm. Total budget under 4,000 tokens.

**Fleet-mode contract** — delivered to agents working across or governing the platform. Adds full weight class validation, cross-airspace dep resolution, and zone lock table checks. All agents operating under gndctrl receive this standing contract in fleet mode, plus the airspace map and cross-airspace dep rules.

```
## gndctrl Protocol

You are operating in a gndctrl-governed codebase.

Before modifying any code:
1. Identify your weight class (Super / Heavy / Medium / Light / Ultralight)
2. Identify the @gndctrl:zone marker for each file you intend to edit
3. Check the zone's minimum_agent_class — if your class is insufficient, do not proceed. Report the required class and hold.
4. Load the zone's documentation from the .gndctrl file
5. Check the zone's stability tier and act accordingly
6. Resolve the zone's deps[] list and load docs for any sensitive/locked deps
7. In fleet mode: for any cross-airspace dep, load that airspace's .gndctrl first
8. Confirm your planned actions stay within your authorised zone boundary

When you encounter a @gndctrl:node marker:
- Read the risk level before modifying the function
- Check the touches[] list — if you are adding new system touches, flag it
- Do not change a function's external signature without reading all zones that depend on it
- Load the corresponding logbook entry if one exists (matched by CRID)

When you implement a workaround, write a non-obvious function, or take a calculated risk:
- Place a @gndctrl:node marker on the function with a new CRID
- Single mode CRID format: ZONE_ABBREV-YYYYMMDD-SEQ
- Fleet mode CRID format: AIRSPACE-ZONE_ABBREV-YYYYMMDD-SEQ
- Create the corresponding logbook entry in /logbook before the task is considered complete
- Pre-flight will check for CRIDs in node markers without matching logbook entries and flag them as integrity violations

You must NEVER:
- Attempt to enter a zone requiring a higher weight class than your own
- Modify code in a locked zone without human clearance
- Write to another airspace's locked or sensitive zone without explicit cross-airspace clearance [fleet]
- Add a dependency on a deprecated zone
- Introduce a library not in the tool registry without flagging it first
- Leave a @gndctrl:zone START marker without a matching END marker
```

### Background Maintenance Agents

gndctrl is self-maintaining via two background agents. In fleet mode both agents operate at the project level and optionally at the fleet level.

**gndctrl Auditor**
Runs after every commit or agent session end.
- Validates all zone START markers have a matching END
- Validates all node IDs are namespaced under a valid zone
- In fleet mode: validates cross-airspace zone references resolve to real zones
- Checks zone index matches actual zones found in code
- Verifies declared deps[] still reflect actual import/call relationships
- Flags orphaned markers (pointing to functions that no longer exist)
- Detects circular dependencies — cross-airspace circular deps flagged as critical
- Validates all CRIDs in node markers have matching logbook entries
- Updates zone index and flags drift in open questions

**gndctrl Writer**
Runs when an agent session contains a novel structural decision.
- Reads session log for flagged decisions and resolutions
- Appends structured records to the project decision log
- Creates logbook entries (with CRID) for any node markers placed during the session
- In fleet mode: proposes cross-airspace patterns to the master known solutions queue
- Proposes generalizable resolutions for human review before adding to master known solutions
- Updates zone gotchas lists from documented issues
- Keeps open questions current

### Record Formats

**Decision Log Entry**
```yaml
record_id: AUTH-RATIONALE-001
airspace: AUTH                  # omit in single mode
date: 2026-03-23
zones_affected: [AUTH://AUTH_CORE]
summary: Chose JWT over session cookies for stateless horizontal scaling
decision: Use RS256-signed JWTs with 15-minute expiry and 7-day refresh window
rationale: |
  Session cookies require sticky sessions or shared session store.
  JWT allows any node to verify auth independently.
alternatives_considered:
  - Session cookies with Redis store — rejected, Redis single point of failure
  - Opaque tokens with introspection — rejected, added latency per request
open_questions:
  - Should we implement token rotation on refresh?
```

**Known Solution Entry (Master)**
```yaml
pattern_id: PATTERN_001
contributed_by: airspace=PMT, project=payment-service    # airspace omitted in single mode
date: 2026-03-23
problem: Race condition in concurrent webhook processing causing duplicate payment reconciliation
solution: |
  Acquire distributed lock keyed on webhook event ID before reconciliation.
  Use Redis SETNX with TTL=30s. If lock not acquired, return 409 and let provider retry.
  Reconciliation function must release lock in finally block.
applicable_to: [PMT://STRIPE_SYNC, PMT://WEBHOOK_HANDLER]
human_verified: false
```

### Version Compatibility

Each `.gndctrl` document carries a spec version. Agents check compatibility at pre-flight. In fleet mode, all project `.gndctrl` files must be compatible with the master spec version.

```
.gndctrl @ spec 0.1.x → compatible
.gndctrl @ spec 0.2.x → agent flags incompatibility, does not proceed
```

Markers may carry explicit spec version for forward compatibility:
```python
# @gndctrl:zone START | id=AUTH://AUTH_CORE | deps=[] | stability=stable | gndctrl_spec=0.1.0
```

---

## Positioning

### The Gap gndctrl Fills

| Tool | What it does | What it doesn't do |
|---|---|---|
| **Agent OS** | Extracts coding standards into markdown, injects them into context | No enforcement, no zone awareness, no runtime locking, no scale model |
| **GitAgent** | Defines agent identity, values, and capabilities as a portable format | No codebase annotation, no stability tiers, no task dispatch, no fleet model |
| **gndctrl** | Annotates the codebase itself, enforces access tiers, locks zones at runtime, scales from single project to fleet | — |

**Agent OS** defines what the agent should know before it starts.
**GitAgent** defines what the agent is.
**gndctrl** defines what the codebase is — and enforces it, at any scale.

They are complementary, not competing. gndctrl exports to GitAgent format and works alongside Agent OS standards.

### One-liner
> "gndctrl is Ground Control for your codebase — zone-based stability annotations that any AI agent understands, enforced at runtime, from a single project to a full dev platform."

---

## Planned Product Structure

```
gndctrl/
├── spec/               # The open standard — zone marker format, .gndctrl schema, stability tiers, fleet mode
├── cli/                # gndctrl init / preflight / audit / export
│   ├── init            # Scaffold .gndctrl — detects single vs fleet mode automatically
│   ├── preflight       # Run pre-flight check for a given task
│   ├── audit           # Validate all markers, CRIDs, cross-airspace refs
│   └── export          # Export to GitAgent, Claude Code, Gemini, Codex formats
├── adapters/           # Provider-specific agent contract templates
│   ├── claude/
│   ├── gemini/
│   ├── codex/
│   └── gitagent/
├── logbook/            # Logbook entries (per-project, CRID-indexed)
└── github-action/      # PR validation — block merges touching locked zones, fleet-aware
```

---

## Build Order

### Phase 1 — The Spec ✓ complete (2026-03-23)
- Zone marker format documented as a versioned open standard
- `.gndctrl` file schema defined for both single and fleet mode
- All six stability tiers and enforcement rules defined
- Five zone types and pre-flight contract templates defined
- Airspace ID system and cross-airspace dep syntax defined
- CRID format defined (single and fleet variants)
- Spec implemented inside Chisel as the live battle-test environment

---

> **Internal validation phases (Chisel-first, before any external release):**
> These phases run inside the Chisel fleet. Proof they work in production is the prerequisite for everything below.

### Phase 2 — Enforcement (Auditor)
- `pchisel_agents.py` — Auditor logic: validate zone START/END pairs, node IDs, dep resolution, no circular deps, no orphan nodes, CRID integrity
- `POST /api/pchisel/{name}/audit` endpoint
- Post-session Auditor hook in `chisel-base/backend/routes/chat.py`

### Phase 2.5 — Compact Button Integration
- Update `compact_chat()` to write structured entries to the project `.gndctrl` doc instead of `docs/notes.md`

### Phase 3 — Self-Maintenance (Writer)
- `pchisel_agents.py` — Writer logic: session decisions → decision_log entries, novel node markers → logbook entries
- `POST /api/pchisel/{name}/write` endpoint
- Token metrics logging (pre vs. post-gndctrl baseline)

### Phase 4 — Rollout & Validation
- Upgrade all active project pchisel.md files
- Confirm Auditor runs clean across all annotated projects
- Run full system across multiple real concurrent projects — validate zone locking, pre-flight, dep resolution, Writer

---

> **External launch phases (after Phase 4 proves the system):**

### Phase 5 — The CLI
- `gndctrl init` — scaffold a project, detect single vs fleet mode from folder structure
- `gndctrl audit` — scan codebase, validate all markers, CRIDs, cross-airspace refs, report violations
- `gndctrl preflight` — given a task description, return zone clearance report
- `gndctrl export --format gitagent` — GitAgent compatibility

### Phase 6 — GitHub Action
- On every PR, scan changed files against zone index
- Block merge if changes touch `locked` or `sensitive` zones without a clearance annotation
- In fleet mode: validate cross-airspace refs in changed files resolve correctly
- Comment with the zone report on the PR
- Adoption driver — teams add gndctrl to protect critical code with no other setup required

### Phase 7 — Provider Adapters
- Claude Code adapter (primary — most complete contract)
- Gemini CLI adapter
- Codex adapter
- Copilot compatibility notes

### Phase 8 — Hosted Platform (gndctrl.dev)
- Web dashboard for zone map visualisation — single and fleet views
- Fleet airspace map — visual overview of all projects and their cross-airspace deps
- Lock table monitoring (fleet-wide)
- Knowledge promotion review UI (gndctrl Writer queue)
- Multi-agent scheduler with per-zone, per-airspace dispatch
- This is the commercial layer

---

## Monetisation Strategy (TBD — pre-decision)

**Option A — Open Core**
Spec + CLI + single mode are free and open source. Fleet mode, GitHub Action, hosted dashboard, and multi-agent scheduler are paid. gndctrl.dev is the commercial SaaS.

**Option B — Source Available**
All code is visible but not open source (BSL or SSPL licence). Commercial use requires a paid agreement. Prevents competitors forking and competing directly.

**Decision criteria:** Resolve before any public launch. Lean towards Source Available until ecosystem is established, then consider opening the spec layer fully. Consult IP lawyer before publishing anything publicly.

---

## Name & Brand

**Product name:** gndctrl
**Full name:** Ground Control
**Domain:** gndctrl.dev (confirmed available 2026-03-23)
**Backup:** gndctrl.io (confirmed available 2026-03-23)
**Future:** gndctrl.com — make offer once product has traction
**GitHub:** Personal account for now, migrate to `gndctrl` org when ready to go public

**Why the name:** Ground Control is the ATC authority before anything moves. Before any agent touches any zone, it checks in with gndctrl. The dropped vowel (`ctrl`) signals developer tooling and doubles as a reference to the Ctrl key — control, literally. The ATC metaphor scales naturally from a single project (one airport) to a full platform (regional airspace) without the name losing meaning.

---

## Relationship to Chisel

gndctrl originates from the pChisel context management system built inside Chisel (a personal AI dev platform). Chisel is a fleet mode environment by nature — multiple containerised projects, parallel agents, a master control layer. This makes it the ideal battle-testing ground for gndctrl's fleet mode before any public release.

**Current implementation state (as of 2026-03-24):**
- `chisel.master.gndctrl` — master fleet document; served to agents at container boot via `GET /api/pchisel/master`
- `pchisel-app.gndctrl` — platform project document with 6 live zones: AUTH_CORE, PROJECT_MGMT, CONTAINER_ORCHESTRATION, KEY_STORE, ROUTING, GNDCTRL_API
- `logbook/` — 3 CRID-indexed entries in production (CHI-AUTH-20260324-001, CHI-CONT-20260324-001, CHI-CONT-20260324-002)
- `gndctrl-agent-contract.md` — fleet-mode contract deployed to all AI provider paths at container boot
- `gndctrl-agent-contract.md` (single-mode) — contract for tenant project containers using `@gndctrl:zone` markers
- Zone markers in `backend/routes/` (fleet) and `backend/scheduler_dispatch.py`
- Template `project.gndctrl` scaffolded for all new workspace projects

The internal build roadmap (Auditor → Writer → multi-agent routing → full fleet validation across real projects) must complete before any external release or public conversation about the product.

Once proven, gndctrl is extracted as a standalone product. Chisel becomes the reference implementation of fleet mode and the premium hosted environment. gndctrl.dev becomes the public product, with single mode as the accessible entry point and fleet mode as the upgrade path.

**This project is independent of Redbrick.** It is a personal project and must remain private until the monetisation strategy is resolved and the product is ready for public launch.

---

## Glossary

| Term | Definition |
|---|---|
| **Airspace** | A project or environment in fleet mode, identified by a short airspace ID |
| **Airspace ID** | A 3–4 character code that namespaces a project's zones and logbook entries in fleet mode |
| **Zone** | A logical boundary wrapping a functional domain in the codebase |
| **Node** | An individual function or method within a zone, tagged with `@gndctrl:node` |
| **CRID** | Control Record ID — immutable identifier linking a node marker to its logbook entry |
| **Logbook** | The `/logbook` directory containing timestamped markdown entries for non-obvious functions |
| **Logbook entry** | A structured markdown record documenting a specific non-obvious function or workaround |
| **Pre-flight** | Mandatory context loading sequence before an agent begins any task |
| **Clearance brief** | The output of pre-flight — agent class confirmed, authorised zones, constraints, gotchas, green light |
| **Guardrail** | A rule constraining agent behaviour based on zone stability, weight class, and dep declarations |
| **Weight class** | Agent capability classification (Super / Heavy / Medium / Light / Ultralight) modelled on aviation aircraft weight categories |
| **minimum_agent_class** | Zone or node field declaring the lowest weight class permitted to enter that zone |
| **Hot memory** | Always-loaded context at pre-flight — conventions, zone index, airspace map |
| **Cold memory** | On-demand context — full zone docs, dep chain docs, logbook entries, known solutions |
| **Dep chain** | The full transitive dependency graph of zones involved in a given task |
| **Cross-airspace dep** | A dependency from one project's zone onto another project's zone in fleet mode |
| **Single mode** | One project, one `.gndctrl`, no fleet overhead |
| **Fleet mode** | Multiple projects, master `.gndctrl`, airspace IDs, cross-airspace deps |
| **gndctrl Auditor** | Background agent (Ultralight class) that maintains structural integrity of all markers, CRIDs, and cross-airspace refs |
| **gndctrl Writer** | Background agent (Ultralight class) that captures decisions, workarounds, and known solutions into the logbook and master docs |

---

## Status
- [x] Register gndctrl.dev
- [x] Write gndctrl-spec v0.1.0 (this document)
- [x] Build zone marker format into Chisel as fleet mode battle test (Phase 1 complete 2026-03-23)
  - 6 zones live in pchisel-app, master + project .gndctrl files, logbook with 3 entries, agent contracts deployed
- [x] Create private GitHub repo — https://github.com/internetsguy/gndctrl
- [x] Build gndctrl CLI v0.1.0 — init, audit, preflight, zones (2026-03-27)
- [ ] Phase 2 — Auditor enforcement (in progress internally)
- [ ] Phase 3 — Writer self-maintenance
- [ ] Phase 4 — Fleet validation across multiple real projects
- [ ] Build GitHub Action (single mode first)
- [ ] Add fleet mode to GitHub Action
- [ ] Decide monetisation model
- [ ] Consult IP lawyer before public launch
- [ ] Public launch
