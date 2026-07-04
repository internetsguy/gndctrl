# gndctrl — How It Works, and Why It Beats Plain Agents

> Air Traffic Control for agentic codebases.
> **The codebase should decide what agents can touch.**

This document is the source-of-truth explainer for the site. It covers what gndctrl is,
the mechanism behind it, and — the part most people ask about — what it actually gives you
that a plain agent with a good prompt does not.

---

## The one-liner

**gndctrl is a governance layer you embed *in the codebase itself*** — stability annotations
and persistent memory that any AI agent reads without an SDK, follows as clearance rules, and is
*enforced against at runtime*. It scales from one developer with one project to a platform running
many agents across many services, on the same mental model.

Ground Control for your codebase: agents file a flight plan, get cleared into the zones they're
allowed to touch, and leave a logbook entry behind so the next agent starts where they stopped.

---

## Why this exists

Two things changed once agents got good:

1. **Velocity stopped being the bottleneck — trust did.** An agent can produce a correct-looking
   diff in seconds. The expensive question is no longer "can it write the code" but "is it allowed
   to touch *this* code, and does it know why this code is the way it is."
2. **Agent sessions are stateless.** The hard-won reason a function is "weird" — the workaround, the
   fragile ordering, the thing that breaks billing if you change it — lives in someone's memory or a
   buried PR comment. The next agent (or the next *model*) starts blind and re-learns it by breaking it.

Plain prompt files (a `CLAUDE.md`, an `AGENTS.md`, a coding-standards doc) try to patch this by
stuffing rules into context. But a rule in a prompt is **advice the agent can skip**, it has **no
idea which part of the codebase it's standing in**, and it **forgets everything when the session ends**.

gndctrl fixes the substrate instead of the prompt: it gives the codebase a voice that survives
session resets and tool switches, and it makes the important rules *non-optional*.

---

## How it works — the six mechanisms

### 1. The codebase annotates itself (zones & markers)

Governance lives in three layers, in the repo:

- **`.gndctrl`** — one file at the project root. A zone registry: each zone is a set of path
  patterns plus its stability tier, dependencies, gotchas, decisions, and logbook pointers.
- **`@gndctrl:zone START / END`** — inline markers that wrap a region of a file when one file spans
  more than one zone.
- **`@gndctrl:node`** — a marker on a single non-obvious function: its risk level, the external
  systems it `touches=[...]`, and a `crid=` linking it to a logbook entry.

The point: an agent doesn't have to *infer* the architecture by reading 50 files. It reads a map.

### 2. Stability tiers — clearance, like airspace

Every zone carries one of six tiers. Each maps to an air-traffic-control class, which is the whole
metaphor: *how controlled is this airspace?*

| Tier | ATC equivalent | What an agent may do |
|---|---|---|
| `experimental` | Uncontrolled | Act freely |
| `active` | Class E | Normal work; verify deps aren't broken |
| `stable` | Class C/D | Read the zone doc before structural changes |
| `sensitive` | Restricted | Read full zone + dependency-chain docs; gated by agent capability |
| `locked` | Prohibited | Humans only — agent surfaces a diff for review, never edits |
| `deprecated` | Decommissioned | No new dependencies; suggest the migration path |

The tier isn't decoration — it changes what the tooling *allows*, not just what it suggests.

### 3. Pre-flight — load the right context, cheaply

Before an agent works, it runs a short, bounded sequence: load the `.gndctrl`, find the zone(s) the
task touches, pull only those zones' dependency docs and logbook entries, check it's allowed in, and
issue a one-paragraph clearance brief.

This is also where the **token economy** comes from. Instead of dumping a 40k–200k-token codebase
into context to "understand" it, the agent reads a ~1–4k-token map and pulls *only the relevant
section*. Targeted, not exhaustive — once per session, not per question.

### 4. Persistent memory — the logbook

Three durable stores, all in the repo, all readable by the next agent or human:

- **Logbook** (`/logbook`, CRID-indexed) — per-function institutional memory: the workaround, the
  landmine, "what breaks if you change this." Loaded on demand at pre-flight.
- **decision_log** — why an architectural choice was made, what was considered, what it affects.
- **known_solutions** — generalizable fixes, so a solved problem stays solved across the team/fleet.

A **CRID** (Control Record ID) is the immutable link between a marker in
the code and its logbook entry — e.g. `AUTH-20260430-001` in single mode (zone abbreviation +
date + sequence), or `PMT-STR-20260430-001` in fleet mode (airspace `PMT` + zone abbreviation
`STR` for `STRIPE_SYNC` + date + sequence). The code says *what*; the logbook says *why, and
what not to touch*.

### 5. Enforcement — advice vs. a hard gate

This is the line between gndctrl and a prompt file. gndctrl enforcement is two-layer:

- **Soft** — the contract every agent loads tells it the rules (provider-agnostic; see §7).
- **Hard** — platform-level guardrails the agent *cannot talk its way past*: file watches, commit
  hooks, session scoping, and tool-call interception.

**This is live, not theoretical.** On the reference deployment, a pre-tool hook sits in front of
every agent edit. If an agent tries to modify a file inside a governed zone *before it has read that
zone's `.gndctrl`*, the edit is **denied** — the agent is handed back the reason and told to read the
map first, then retry. The result: an agent physically cannot "act first, read the architecture last."
The most common, most expensive agent failure — drifting from the design because it never looked —
is removed at the tool layer, not requested in a prompt.

A locked zone is the same idea at the top of the dial: the agent surfaces a diff and stops. Humans
decide.

### 6. Weight classes — provider-agnostic capability gating

Agents differ in capability, so zones declare a **`minimum_agent_class`** — a floor, not a ceiling. The class is declared per session; model names are never baked into the rules, only into a *suggested mapping* your deployment maintains (models turn over, your governance shouldn't).

| Weight class | Examples (suggested mapping — yours may differ) |
|---|---|
| Ultralight | Scripted/rule-based (gndctrl's own Auditor/Writer) |
| Light | Small fast local models (3–7B) |
| Medium | Gemini, GPT-class mid-size, Copilot |
| Heavy | Claude Sonnet, large capable models |
| Super | Frontier reasoning (Claude Opus) |

A heavier agent can always enter a lighter zone; a too-light agent is held at pre-flight until a
capable one is available. Crucially, the rules are written **once** and apply to **any** provider —
Claude, Gemini, Copilot, Codex, a local model — without rewriting your guardrails per tool.

### 7. It maintains itself (the background agents)

gndctrl ships two Ultralight agents so the system doesn't rot:

- **Auditor** — validates that every marker is well-formed, every `@gndctrl:node` has a logbook
  entry, every zone resolves. Drift in the governance itself gets caught.
- **Writer** — appends decisions and creates logbook entries as work happens, so memory is captured
  in the same motion as the change, not as a forgotten end-of-session chore.

---

## It's software, not a prompt

Here's the distinction that decides whether gndctrl is worth *installing* rather than
copy-pasting: **a `CLAUDE.md` is text you drop into a chat box. gndctrl is a program that
reads your code.** The markers and the `.gndctrl` file aren't instructions the model follows
out of goodwill — they're a **data format with a parser, a schema validator, an auditor, a
dependency resolver, and a runtime enforcer** behind them. You can copy a prompt into any tool
in five seconds. You can't copy *enforcement* — enforcement has to run.

What's actually in the package:

**A parser, not a reader.** Markers are extracted by a real scanner (`@gndctrl:zone START/END`,
`@gndctrl:node`) and the grammar is checked — a node id must match `ZONE.function` or
`AIRSPACE://ZONE.function` or it's rejected. The map is structured data, validated as data.

**A schema, not conventions.** Stability tiers, zone types, and weight classes are validated
against fixed sets — six stability tiers, five agent classes with a defined rank order, five
zone types. An unknown tier or a mistyped class is a hard validation error, not a line that
gets quietly ignored. Clearance can be *computed* because the inputs are *typed*.

**An auditor with CI exit codes.** `gndctrl audit` runs deterministic integrity checks across
the whole tree and exits non-zero on failure — wire it into CI and a broken governance map
fails the build:

| Check | What it catches |
|---|---|
| A1 | Zone `START`/`END` markers that don't pair up |
| A2 | A node pointing at a zone that doesn't exist |
| A3 | A `@gndctrl:node` CRID with no matching logbook entry |
| A4 | A malformed CRID |
| A5 | A duplicate CRID — two markers claiming the same control record |
| A6 | Dependency resolution — including **circular-dependency** detection |
| A7 | Declared `deps[]` that have drifted from actual import/call relationships |
| A8 | Orphaned markers — a node pointing at a function that no longer exists |
| A9 | A zone that depends on a `deprecated` zone |
| A10 | Zone-index drift — the map and the code have diverged |

It speaks `--format json` for pipelines, and it leaves a record. Real audit logs from the
reference deployment read: *"Files scanned: 125 · Zones: 4 · Nodes: 2 · ✓ Clean."* That's a
program executing over a codebase — not a model promising it read the rules.

**A pre-flight resolver.** `gndctrl preflight --zones … --agent-class …` walks the transitive
dependency chain for the zones a task touches and decides, in code, whether the agent's weight
class clears it — returning the reason when it doesn't. The clearance brief is the return value
of a function, not a vibe.

**A runtime tripwire.** The enforcement hook is ~120 lines that sit in front of every
`Edit`/`Write`: it locates the governing `.gndctrl`, inspects the session transcript to confirm
it was actually read, and returns a structured `deny` with a reason if it wasn't —
deterministically, every time. It fails *closed* on the one thing it's certain about ("you
didn't read the map") and *open* on everything else, so it gates without getting underfoot.

**A scaffolder.** `gndctrl init` writes the starting `.gndctrl` and `logbook/`, auto-detecting
single vs. fleet mode.

**Why this is the whole point:** an instruction file is portable precisely because it's inert —
it does the same nothing everywhere. gndctrl is worth downloading because it *does* the things a
prompt can't: it parses your governance, validates it, **fails your build when it rots**, and
**blocks the edit when an agent skips the map**. That isn't a paragraph you paste into a system
prompt. It's a tool you run — in CI, in a commit hook, and in front of the agent.

---

## The token question, answered with production data

The single most common objection: *"If every agent has to read the `.gndctrl` map at the
start of every session, isn't that burning tokens?"* It's the right question — and the
reference deployment's own metering answers it. **No. Reading is the cheap part.**

Modern agent runtimes cache context. The map you read once is reused on every subsequent
turn at no charge, and the meter that matters — what counts against a usage budget — bills
only the **non-cached input plus the model's output.** So the cost of an agent session
isn't what it *reads*; it's what it *writes* (its reasoning, tool calls, and edits).

Real numbers from the reference deployment — **325 metered agent turns, ~244 million tokens
processed over roughly a month:**

| Where the tokens went | Share |
|---|---|
| Reused cached context (not charged) | 95.5% |
| Fresh reads — files, the `.gndctrl`, logbook (not charged) | 3.5% |
| Charged **output** (what the agent wrote) | 1.0% |
| Charged **input** | **0.01%** |

- **98.98% of every token processed is cached context** — read once, reused without charge.
- Only **~1%** is ever metered, and **99.3% of that is the agent's own output.**
- **Average metered input: 56 tokens per turn**, regardless of how much the agent read.

And reading volume simply does not move the bill. Two real single turns from the logs:

> One turn pulled **2,871,729 tokens** of context into the model and was metered for
> **1,663** input tokens — a ~1,700:1 read-to-charge ratio. Another ingested **2.83 million**
> tokens and was charged **32**.

This is *why* the pre-flight design is token-smart, not token-expensive. Forcing a read-first
map doesn't add cost — the read is cached and effectively free against the budget. What a good
map removes is the *expensive* behavior: an agent blindly grepping and re-reading its way
around an unfamiliar tree, burning a fresh **output**-heavy turn on every guess and every
wrong path. The map trades cheap (cached) reading for fewer charged (output) turns.

> **98.98% of every token our agents process is cached context, reused without charge. You
> pay for what an agent writes, not what it reads — so handing it the map is the cheap part.**

One caveat the spec now enforces: caching only pays while the map is **byte-identical** between
reads. That's why the spec's *Cache-Stable Documents* rules exist — volatile content (timestamps,
open questions) lives at the bottom of the `.gndctrl`, runtime lock state lives in a separate
gitignored `.gndctrl.locks` file, and any tool that rewrites the document must preserve ordering.
A map that churns at the top of the file is a map you pay to re-read.

---

## What makes it special vs. plain agents

Put plainly — a prompt file is **advice, context-blind, and forgetful.** gndctrl is **enforced,
zone-aware, and persistent.**

| | Plain agent + prompt file | gndctrl |
|---|---|---|
| Rules | Advice the agent can skip | Enforced at the tool/commit/session layer |
| Architecture awareness | Infers it by reading files | Reads a zone map; knows where it's standing |
| Memory across sessions | None — re-learns by breaking things | Logbook + decision_log + known_solutions, in-repo |
| Works across providers | Re-write rules per tool | One model, any agent, via weight classes |
| Context cost | Dump the whole repo | ~1–4k-token targeted pre-flight |
| Scale | Breaks down with parallel agents | Single → fleet on the same mental model |

The four differentiators, each with its proof:

1. **Enforcement, not advice.** Sensitive/locked zones and the pre-tool read-gate *block* the edit.
   (Proven in production: agents are denied edits to a zone until they've read it.)
2. **Persistent institutional memory.** The CRID/logbook system means the next agent — or the next
   model entirely — starts informed about the landmines, instead of stepping on them.
3. **Provider-agnostic.** Weight classes map any agent to a tier; switching from Claude to Gemini to
   a local model doesn't mean rewriting your safety rules.
4. **Scales solo → fleet.** Single mode is one `.gndctrl` file with zero ceremony. Fleet mode adds
   airspaces, cross-airspace dependencies, master governance, and a zone-lock table for parallel
   agents — *the same concepts, a bigger map.*

---

## Single mode → fleet mode (the upgrade path)

You don't adopt a platform. You add one file.

- **Single mode** — `airspace: null`. One `.gndctrl`, zones, markers, a logbook. A solo dev gets the
  token savings and a coherent agent on day one, with no overhead.
- **Fleet mode** — each project becomes an **airspace** (a short ICAO-style ID). Zones and CRIDs are
  namespaced; a master document governs cross-airspace dependencies; a lock table keeps parallel
  agents out of each other's way. Same markers, same tiers, same pre-flight — just coordinated across
  services and many simultaneous agents.

The mental model never changes. That's the design.

---

## Concrete wins (the developer-facing summary)

- **Lower context cost** — a targeted pre-flight (~1–4k tokens) instead of loading the whole codebase
  (tens to hundreds of thousands of tokens), once per session.
- **Fewer repeated mistakes** — landmines are recorded once and read forever; agents stop re-breaking
  the same fragile code.
- **Real guardrails** — the dangerous edits are *blocked*, not just discouraged.
- **One rulebook, every agent** — Claude, Gemini, Copilot, Codex, local models — same governance.
- **An audit trail** — every non-obvious change leaves a CRID and a logbook entry. You can see what
  changed, why, and what it touched.

---

## Status / using it today

gndctrl is **spec-first**: the format works right now, by hand, with any agent — you can write a
`.gndctrl`, add markers, and point your agent's system prompt at the contract today, no CLI required.
The CLI (`gndctrl init`, audit/write tooling) and the public repo are the packaging layer on top.

> **Ship fast. Keep control.**
