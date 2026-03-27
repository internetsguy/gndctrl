# gndctrl GitHub Action

**Planned.** On every PR, scan changed files against the zone index and block merges that touch `locked` or `sensitive` zones without a clearance annotation.

## Planned Usage

```yaml
# .github/workflows/gndctrl.yml
name: gndctrl zone check
on: [pull_request]

jobs:
  zone-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: gndctrl/gndctrl-action@v1
        with:
          mode: single          # or 'fleet'
          block-on: sensitive   # or 'locked-only'
```

## What It Does

1. Parses `.gndctrl` to build the zone index
2. Scans all files changed in the PR against zone path patterns and inline markers
3. Checks stability tier of each touched zone
4. Blocks merge if any touched zone is `locked` (no clearance) or `sensitive` (no review annotation)
5. Comments on the PR with the zone report

## Fleet Mode Addition

- Validates cross-airspace zone references in changed files resolve correctly
- Checks that no file writes to another airspace's `locked` zone without explicit clearance

## Adoption Note

The GitHub Action is the primary adoption driver — teams add gndctrl to protect critical code with no other setup required. No CLI, no platform, no agents needed. Just zone markers in the code and the Action in CI.
