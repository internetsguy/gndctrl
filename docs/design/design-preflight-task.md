# Design: `gndctrl preflight --task` — Task-Resolved Clearance

**Status:** Draft for implementation · 2026-07-03
**Target:** gndctrl CLI (src/gndctrl), Phase 5
**Depends on:** existing preflight resolver, zone registry parser, `.gndctrl.locks`

---

## Goal

Let an agent hand the CLI a plain-language task description and get back a complete,
machine-readable clearance brief — matched zones, resolved dep chain, weight-class verdict,
lock status, and the exact list of things it must read — **without the agent ever loading the
full zone registry or composing the brief itself.** The clearance brief becomes the return
value of a function, not a paragraph the agent writes (this is the token lever: fewer
output-heavy turns).

Deterministic, lexical, no LLM required. An optional LLM-assist can come later behind a flag.

**Who invokes this:** on pChisel, only the agent, the PreToolUse hook, or the platform — the
end user never sees a terminal or a raw brief. Everything user-facing is the agent narrating
`user_summary` (below) in chat, or the dashboard rendering the JSON. The `--format text`
rendering exists solely for the standalone/developer audience.

---

## CLI

```
gndctrl preflight --task "<description>" [options]

Options:
  --agent-class <class>     ultralight|light|medium|heavy|super (default: from env GNDCTRL_AGENT_CLASS, else unset)
  --zones <IDs>             comma-separated override — skip matching, resolve these zones directly
  --files <paths>           comma-separated file paths the task will touch (strong matching signal)
  --format json|text        default: text (human), json for agents/pipelines
  --min-confidence <0-1>    matching threshold, default 0.5
```

`--task` and `--zones` are mutually exclusive inputs to the matcher; everything downstream
(deps, class, locks, brief) is shared with the existing `preflight --zones` path.

---

## Pipeline

```
1. MATCH    task text (+ --files) → candidate zones with confidence scores
2. RESOLVE  transitive deps[] for matched zones (existing resolver)
3. GATE     weight class check per zone (existing)
4. LOCKS    read .gndctrl.locks, check matched zones + dep chain
5. READS    compute required_reads: zone doc sections + logbook entries by CRID
6. EMIT     clearance brief (text or JSON) + exit code
```

### Step 1 — Zone matching (the new part)

Score each zone in the registry against the task. Signals, strongest first:

| Signal | Score | Notes |
|---|---|---|
| Explicit zone ID in task text (`AUTH`, `PMT://STRIPE_SYNC`) | 1.0 | Case-sensitive on the ID token |
| `--files` path matches a zone's `paths[]` pattern | 1.0 | fnmatch against each pattern |
| File path *mentioned in task text* matches `paths[]` | 0.9 | Extract path-like tokens (`contains / or matches *.ext`) |
| Keyword overlap with `brief` | per-hit 0.3, cap 0.8 | Lowercased, stopwords stripped, stemmed-ish (strip s/ing/ed) |
| Keyword overlap with `description` | per-hit 0.2, cap 0.6 | Same normalisation |
| Keyword overlap with zone ID tokens (`AUTH_CORE` → auth, core) | per-hit 0.3, cap 0.6 | |
| Keyword overlap with `gotchas` / `decisions` text | per-hit 0.1, cap 0.3 | Weak signal, tie-breaker only |

Zone score = max(signal scores) + 0.1 × (count of distinct other signals ≥0.2), capped 1.0.

Outcomes:
- **≥ min-confidence:** zone is matched.
- **No zone ≥ threshold but some ≥ 0.25:** ambiguous — return candidates, exit 4, do not clear.
  Each candidate carries its `brief` so the agent can ask the user a plain-language question
  ("Is this about the login system or the payment handling?") and re-run with `--zones` —
  the user picks in conversation; the terminal flag is the agent's job.
- **Nothing ≥ 0.25:** no governed zone matched — report "task appears to touch no governed
  zone; treat as stability=active", exit 0 with `matched_zones: []` and a note.

Determinism rule: identical registry + identical task string ⇒ identical output. No
randomness, no model calls.

### Step 5 — required_reads

For each matched zone and every `sensitive`/`locked` zone in its dep chain:
- the zone's doc section (pointer: file + YAML path, e.g. `.gndctrl#zones/AUTH`)
- every logbook entry whose CRID appears on a node inside the zone's paths (scanner already
  extracts these) — return the actual file path so the agent can `cat` it directly

---

## JSON output schema

```json
{
  "gndctrl_spec": "0.1.0",
  "generated": "2026-07-03T14:02:11Z",
  "mode": "single",                       // "single" | "fleet"
  "airspace": null,                       // fleet: e.g. "CHI"
  "task": "add password reset endpoint",
  "agent_class": "heavy",                 // null if not declared
  "matched_zones": [
    {
      "id": "AUTH",
      "confidence": 0.86,
      "matched_on": ["brief_keyword:password", "id_token:auth"],
      "stability": "sensitive",
      "minimum_agent_class": "heavy"
    }
  ],
  "candidates": [],                       // populated only on exit 4 (ambiguous)
  "dep_chain": [
    { "id": "SESSION", "via": "AUTH", "stability": "stable", "cross_airspace": false }
  ],
  "clearance": {
    "status": "cleared",                  // "cleared" | "denied" | "held_locked" | "ambiguous" | "ungoverned"
    "per_zone": [
      {
        "id": "AUTH",
        "verdict": "cleared",             // "cleared" | "denied_class" | "held_locked" | "locked_zone_diff_only"
        "reason": null,                   // e.g. "requires heavy, agent is medium"
        "required_class": "heavy"
      }
    ]
  },
  "locks": {
    "lock_file": ".gndctrl.locks",
    "conflicts": []                       // [{zone, held_by_session, since}]
  },
  "required_reads": [
    { "kind": "zone_doc", "zone": "AUTH", "pointer": ".gndctrl#zones/AUTH" },
    { "kind": "logbook", "crid": "AUTH-20260324-001", "path": "logbook/AUTH-20260324-001-session-edge-case.md" }
  ],
  "constraints": [
    "AUTH is sensitive: read full zone doc + dep docs, surface risk summary before acting",
    "Cross-zone edits outside AUTH, SESSION must be flagged before proceeding"
  ],
  "gotchas": [
    { "zone": "AUTH", "text": "Session tokens are HttpOnly cookies — never exposed to frontend JS." }
  ],
  "token_estimate": { "hot": 640, "cold_required": 1810, "total": 2450 },
  "brief_text": "CLEARED — heavy agent, zones AUTH (+dep SESSION). Sensitive zone: read 1 zone doc + 1 logbook entry before editing. No locks held.",
  "user_summary": "This change touches your login system, which is marked as needing extra care. I've loaded its safety notes and I'm cleared to proceed."
}
```

`brief_text` is the technical one-paragraph summary — agent/developer-facing, quotable in a
clearance confirmation.

`user_summary` is the **plain-language** version for non-technical end users: no zone IDs,
no gndctrl jargon, no class names. Template rules: name the affected area in everyday terms
(derived from the zone `brief`), state the care level ("needs extra care" for sensitive,
"can't be changed without your approval" for locked), and state the outcome ("cleared to
proceed" / "I need your approval first" / "this needs a more capable agent"). On pChisel,
this is the string the agent speaks in chat.

`token_estimate` is chars/4 over the pointed-to content; it's the number that feeds the
future `gndctrl metrics` command.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Cleared (or ungoverned — see `clearance.status`) |
| 1 | Error (bad args, unreadable `.gndctrl`, schema failure) |
| 2 | Denied — agent class below a zone minimum |
| 3 | Held — a required zone is locked by another session |
| 4 | Ambiguous match — candidates returned, human/agent must pick with `--zones` |

## Contract integration

Single-mode contract Step 2/3 collapses to:
```
gndctrl preflight --task "<user's request>" --agent-class <class> --format json
```
Then: read everything in `required_reads`, obey `constraints`, quote `brief_text`. Fleet
contract identical plus master load in Step 1.

## Tests (minimum)

- Explicit zone ID in task → confidence 1.0, deterministic across runs
- `--files backend/routes/auth.py` matches AUTH via path pattern
- Task matching nothing → `ungoverned`, exit 0
- Two zones both scoring 0.4 with threshold 0.5 → exit 4 with both as candidates
- Medium agent + heavy zone → exit 2, `denied_class` with required class in reason
- Lock held on dep-chain zone → exit 3
- JSON output validates against the schema above; `--format text` renders same data
- `user_summary` contains no zone IDs, class names, or gndctrl terms (denylist assertion)
- Denied and locked verdicts each produce a `user_summary` with an actionable next step
