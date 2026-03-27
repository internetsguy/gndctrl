# gndctrl CLI

**Planned.** This directory will contain the gndctrl CLI tool.

## Planned Commands

```bash
gndctrl init              # Scaffold .gndctrl — detects single vs fleet mode automatically
gndctrl audit             # Validate all markers, CRIDs, cross-airspace refs, report violations
gndctrl preflight <task>  # Given a task description, return zone clearance report
gndctrl export --format gitagent  # Export to GitAgent / Claude Code / Gemini / Codex formats
```

## Distribution Targets

- Shell installer (`curl -fsSL https://gndctrl.dev/install.sh | sh`)
- npm global package (`npm install -g gndctrl`)
- pip package (`pip install gndctrl`)
- Docker image (`gndctrl/cli:latest`)

## Implementation Notes

- Single binary preferred (Go or Rust) for easy distribution across CLI environments
- Python fallback acceptable for initial prototype given pChisel's Python-first environment
- Must work inside Docker containers without root
