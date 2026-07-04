# Design documents — roadmap, NOT shipped features

The documents in this directory are **Phase-5 design drafts**. The commands they describe do
not exist in the CLI yet — do not reference them in contracts, agent prompts, or user docs as
available functionality.

| Doc | Proposes | Status |
|---|---|---|
| `design-preflight-task.md` | `gndctrl preflight --task "<text>"` — automated clearance briefs from plain-language task text | Draft for implementation (Phase 5) |
| `design-init-analyze.md` | `gndctrl init --analyze` — deterministic repo scan proposing a draft zone map (`.gndctrl.draft`) | Draft for implementation (Phase 5) |

## CLI roadmap gaps (known, deliberate)

Recorded here so they aren't mistaken for regressions:

- `gndctrl audit` does not yet implement the spec rev-2 audit items **A5** (duplicate CRIDs),
  **A7** (declared `deps[]` drifted from real import/call relationships), or **A8** (orphaned
  markers pointing at deleted functions).
- No `.gndctrl.locks` tooling yet (lock create/inspect/expire). The spec's lock-file rules are
  honored by agent contracts (read + respect), but nothing machine-manages the file.
- The two Phase-5 commands above.

## Feedback queued for the next spec revision

Weak points found during the 2026-07-04 rev-2 integration review, deferred to the spec author:

1. **No formal zone schema table** — node markers have a field-reference table; zones are only
   shown by example. Required vs optional fields and valid values are ambiguous for tooling and
   hand-authors alike.
2. **"Non-obvious" is undefined** — it is the trigger for CRID/logbook obligations, but the spec
   never defines it, so agents under- or over-document. Needs criteria or examples.
3. **No-`.gndctrl` flow is vague** — contracts say "treat all code as active + recommend
   `gndctrl init`", but don't say what happens when the user declines governance outright.
