# Design: `gndctrl init --analyze` — Proposed Zone Map for Existing Repos

**Status:** Draft for implementation · 2026-07-03
**Target:** gndctrl CLI (src/gndctrl), Phase 5
**Depends on:** existing `init` scaffolder, registry schema

---

## Goal

Remove the biggest adoption barrier: producing a zone map for an existing repo from scratch.
`--analyze` scans the repo with cheap, deterministic signals and emits a **draft** zone map
plus machine-readable evidence for a reviewer to approve.

**Two consumption surfaces — design for both:**

1. **Standalone CLI (public product):** a developer runs it in a terminal, reads the report,
   edits the draft, renames it to adopt.
2. **pChisel (reference platform):** the end user **never touches a terminal and never reads
   a file.** The platform or agent invokes the CLI; the agent presents the proposed zones
   conversationally ("I found 4 areas — your login code looks sensitive, want me to protect
   it?") or the dashboard renders them from the JSON report; acceptance happens via an agent
   action or API call, not a rename. Every output of this command must therefore be fully
   consumable as structured data — the markdown report is a convenience for surface 1, never
   the only artifact.

The analyzer does not need to be smart — it needs to be a decent first draft that takes a
reviewer (human-in-terminal or agent-in-chat) minutes to approve instead of hours to author.

Hard rules:
- **Read-only against the repo.** Never touches source files, never writes markers.
- **Never overwrites.** Output goes to `.gndctrl.draft` (+ a report). If `.gndctrl` already
  exists, refuse `--analyze` unless `--draft-only` is passed.
- **Everything is a proposal.** Every zone carries a `confidence` and `proposed_by: analyzer`
  annotation. Adoption is explicit: rename for terminal users, `--accept-draft` for
  programmatic callers (see *Acceptance*).
- **No LLM, no network.** Deterministic: same repo state ⇒ same draft.

---

## CLI

```
gndctrl init --analyze [options]

Options:
  --churn-window <days>   git activity window for stability inference (default 90)
  --stale-after <days>    untouched-for-this-long → stable candidate (default 365)
  --no-git                skip git signals (structure + patterns only)
  --max-zones <n>         cap proposed zones, merge smallest into parent (default 12)
  --lang <auto|py|js|go>  import-graph parser selection (default auto by extension census)
  --draft-only            allow running when .gndctrl already exists (writes draft beside it)
  --format json|md|both   report format (default: both; pChisel invokes with json)
```

Outputs:
- `.gndctrl.draft` — valid schema, cache-stable ordering
- `gndctrl-analyze-report.json` — **the primary artifact**: per-zone evidence (signals fired,
  confidence, file counts, churn numbers, proposed stability/class with reasons), structured
  so an agent can narrate it in plain language or a dashboard can render it. Same data model
  as the draft plus an `evidence` block per zone.
- `gndctrl-analyze-report.md` — human-readable rendering of the same data (terminal audience)

## Acceptance

Two paths, same result:

- **Terminal (standalone):** review the draft, edit, rename `.gndctrl.draft` → `.gndctrl`.
- **Programmatic (pChisel / agents):**
  `gndctrl init --accept-draft [--only-zones AUTH,API] [--set AUTH.stability=locked]`
  Validates the draft against the schema, applies any per-zone overrides gathered from the
  in-chat/dashboard review, writes `.gndctrl`, deletes the draft, exits 0. Partial acceptance
  (`--only-zones`) writes the accepted zones and leaves the rest in the draft for a later
  round. This is the path the pChisel agent uses after the user approves in conversation —
  the user answers questions in chat; the agent translates answers into `--accept-draft` flags.

---

## Pipeline

```
1. CENSUS     walk tree (respect .gitignore); count files/lines per directory; detect language mix
2. CLUSTER    propose zone candidates from directory structure
3. PATTERNS   flag sensitive candidates by name/content patterns
4. CHURN      git log → activity per candidate (skipped with --no-git)
5. IMPORTS    lightweight import graph → proposed deps[]
6. ASSIGN     stability + minimum_agent_class per zone from the signal table
7. EMIT       .gndctrl.draft + report
```

### 2 — Clustering heuristics

- Start from top-level source dirs (skip vendored/build: `node_modules`, `.venv`, `dist`,
  `build`, `__pycache__`, `vendor`).
- A directory becomes a candidate zone if it has ≥3 source files **or** ≥200 source lines.
- Recurse one level when a dir is >40% of the repo's lines (split monolith dirs like `src/`
  into `src/api/`, `src/auth/`…).
- Files matching sensitive patterns (step 3) that sit inside a broad candidate get pulled
  into their own zone when they form a coherent sub-path (e.g. `src/**/auth*` → AUTH).
- Zone ID = SCREAMING_SNAKE of the dir/topic name, deduped; `paths[]` = the glob(s) that
  produced the cluster.
- Over `--max-zones`: merge smallest candidates into their parent until under the cap;
  record merges in the report.

### 3 — Sensitive patterns

Filename/path regex (case-insensitive), plus a shallow content grep of matched files:

| Pattern (path or symbol names) | Proposal |
|---|---|
| `auth|session|login|token|password|permission|rbac|acl` | stability=sensitive, class=heavy |
| `payment|billing|stripe|invoice|charge|ledger|payout` | stability=sensitive, class=heavy |
| `secret|credential|keystore|vault|\.env` | stability=locked (config type), class=super |
| `migration|schema|models?\.(py|ts)|alembic` | type=data, +1 stability bump |
| `crypto|signing|jwt|hash` | stability=sensitive, class=heavy |

Content grep is confirmation only (raises confidence), never the sole trigger — avoids
false positives from a stray comment.

### 4 — Churn signals (git)

Per candidate zone, over `--churn-window`:

| Signal | Inference |
|---|---|
| ≥10 commits touching zone paths in window | `active` |
| 1–9 commits in window | `active` (low confidence) or `stable` if older history is long |
| 0 commits in window, history exists | `stable` |
| 0 commits in `--stale-after` days | `stable`, flag in report as *deprecated candidate* — never auto-propose `deprecated` |
| >30% of zone's commits are reverts/fixups (`revert|fix|hotfix` in subject) | +1 stability bump, note "fragile — high fix ratio" as a gotcha seed |

### 5 — Import graph → deps[]

- Python: parse `import`/`from … import` via `ast`; JS/TS: regex `import … from '…'` and
  `require('…')`; Go: `import (...)` block. Resolve relative/module paths to repo files,
  map file → owning zone.
- Zone A lists B in `deps[]` if ≥2 distinct files in A import from B (threshold avoids
  one-off noise). Direction: importer depends on imported.
- Circular candidate deps are reported, not silently written — the draft includes both edges
  with a `# TODO: circular — resolve before audit` comment (A6 will fail otherwise, which
  is the point).

### 6 — Stability & class assignment

Precedence (highest wins): sensitive-pattern proposal → churn inference → default `active`.
A pattern hit never *lowers* stability; churn never overrides a pattern-based `sensitive`.
`minimum_agent_class` follows stability: locked→super, sensitive→heavy, stable→medium,
active/experimental→light. Entry-point files (detected: `main.py`, `app.py`, `index.ts`,
`cmd/*/main.go`, `Dockerfile` CMD target) are listed in `architecture.entry_points`.

### 7 — Draft output shape

```yaml
# .gndctrl.draft — PROPOSED by gndctrl init --analyze on 2026-07-03
# Review every zone. Rename to .gndctrl to adopt. See gndctrl-analyze-report.md for evidence.
airspace: null
version: "0.1.0"

meta:
  project: my-project          # from dir name / pyproject / package.json
  language: python             # from extension census

zones:
  AUTH:
    # proposed_by: analyzer | confidence: 0.85 | signals: path-pattern, churn:active, imports:3
    brief: "PROPOSED — auth, sessions (review this line)"
    stability: sensitive
    type: [code]
    minimum_agent_class: heavy
    deps: [API]
    paths:
      - "src/auth/**"
```

Confidence per zone = weighted blend: pattern hit 0.4, structural coherence 0.3 (files
under one path prefix), churn signal present 0.2, imports resolved 0.1. Shown as a comment,
not a schema field (schema stays clean; the draft suffix carries the "unreviewed" meaning).

---

## Non-goals (v1)

- No inline `@gndctrl:zone`/`@gndctrl:node` marker insertion — path patterns only
- No logbook seeding, no decision_log inference
- No fleet-mode analysis (run per project; master stays hand-authored by the platform)
- No interactive TUI — conversation/dashboard review is the platform's job; the CLI only
  provides the structured data and the `--accept-draft` write path

## Tests (minimum)

- Fixture repo with `auth/`, `billing/`, `ui/` → 3 zones, AUTH+BILLING sensitive/heavy, UI active/light
- `.env` present → locked config zone proposed, class super
- Repo with no git history + `--no-git` → structure-only draft, all `active`, confidences lower
- Existing `.gndctrl` + `--analyze` without `--draft-only` → refuses, exit 1
- `--accept-draft --only-zones AUTH` → `.gndctrl` contains AUTH only; draft retains the rest
- `--accept-draft --set AUTH.stability=locked` → override applied and schema-validated
- JSON report round-trips: draft can be reconstructed from report zones (minus evidence)
- Draft passes `gndctrl audit --format json` schema checks (A-checks that apply to a
  registry with no markers)
- Determinism: two runs on identical tree produce byte-identical drafts (fixed date injected in tests)
