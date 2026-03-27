"""
gndctrl init — scaffold a .gndctrl file and logbook/ directory.
"""
from pathlib import Path

import click


# ── Language and entry-point detection ───────────────────────────────────────

def _detect_language(root: Path) -> str:
    if (root / "go.mod").exists():
        return "go"
    if (root / "Cargo.toml").exists():
        return "rust"
    if (root / "package.json").exists():
        return "typescript" if any(root.rglob("*.ts")) else "javascript"
    if (root / "requirements.txt").exists() or (root / "pyproject.toml").exists():
        return "python"
    return "unknown"


def _detect_entry_point(root: Path, language: str) -> str:
    candidates = {
        "python":     ["main.py", "app.py", "src/main.py"],
        "typescript": ["src/index.ts", "index.ts", "src/main.ts"],
        "javascript": ["src/index.js", "index.js"],
        "go":         ["main.go", "cmd/main.go"],
        "rust":       ["src/main.rs"],
    }
    for candidate in candidates.get(language, []):
        if (root / candidate).exists():
            return candidate
    return {"python": "main.py", "typescript": "src/index.ts",
            "javascript": "src/index.js", "go": "main.go",
            "rust": "src/main.rs"}.get(language, "main.py")


def _suggest_airspace(name: str) -> str:
    """Generate a 3–4 char uppercase airspace ID from a project name."""
    words = name.upper().replace("-", " ").replace("_", " ").split()
    if not words:
        return "PRJ"
    if len(words) == 1:
        return words[0][:4]
    return "".join(w[0] for w in words[:4])


# ── Templates ─────────────────────────────────────────────────────────────────

_SINGLE_TEMPLATE = """\
# {project}.gndctrl
# gndctrl project document — {project}
# gndctrl_spec: "0.1.0"

version: "0.1.0"
airspace: null

meta:
  project: {project}
  description: ""
  language: {language}
  framework: ""
  database: ""
  container: ""

architecture:
  overview: |
    Brief overview of your architecture.
  entry_points:
    - {entry_point}

# ── Zone Registry ─────────────────────────────────────────────────────────────
# Define zones by file path patterns.
# stability:  experimental | active | stable | sensitive | locked | deprecated
# type:       code | design | data | config | docs
# minimum_agent_class: ultralight | light | medium | heavy | super

zones:
  EXAMPLE_ZONE:
    stability: active
    type: [code]
    minimum_agent_class: medium
    deps: []
    paths:
      - "src/*"
    description: "Replace with a real zone description"
    gotchas: []
    decisions: []

decision_log: []
known_solutions: []
open_questions: []
"""

_FLEET_TEMPLATE = """\
# {project}.gndctrl
# gndctrl project document — {project}
# gndctrl_spec: "0.1.0" | airspace: {airspace}

airspace: {airspace}
version: "0.1.0"
master_ref: "{master_ref}"

meta:
  project: {project}
  description: ""
  language: {language}
  framework: ""
  database: ""
  container: ""

architecture:
  overview: |
    Brief overview of your architecture.
  entry_points:
    - {entry_point}

# ── Zone Registry ─────────────────────────────────────────────────────────────
# Deps may reference other airspaces: deps: [{airspace}://ZONE, OTHER://ZONE]

zones:
  EXAMPLE_ZONE:
    stability: active
    type: [code]
    minimum_agent_class: medium
    deps: []
    paths:
      - "src/*"
    description: "Replace with a real zone description"
    gotchas: []
    decisions: []

decision_log: []
known_solutions: []
open_questions: []
"""

_MASTER_TEMPLATE = """\
# master.gndctrl
# gndctrl fleet master — {platform}
# gndctrl_spec: "0.1.0"

version: "0.1.0"
master: true

fleet:
  name: {platform}
  description: "Multi-project platform"
  projects: []

# Add projects as they are initialised:
# projects:
#   - airspace: CHI
#     name: my-service
#     path: ./my-service

decision_log: []
known_solutions: []
open_questions: []
"""


# ── Public API ────────────────────────────────────────────────────────────────

def init_project(root: Path, force: bool = False) -> tuple[Path, Path, bool]:
    """
    Scaffold .gndctrl and logbook/ in *root*.
    Returns (gndctrl_file, logbook_dir, fleet_mode).
    Raises click.ClickException on validation errors.
    """
    existing = list(root.glob("*.gndctrl"))
    if existing and not force:
        raise click.ClickException(
            f".gndctrl already exists: {existing[0].name}  (use --force to overwrite)"
        )

    language = _detect_language(root)
    entry_point = _detect_entry_point(root, language)
    project_name = root.name

    # Detect fleet mode: parent directory already has a .gndctrl
    parent_gndctrls = list(root.parent.glob("*.gndctrl"))
    fleet_mode = bool(parent_gndctrls)

    if fleet_mode:
        master_path = parent_gndctrls[0]
        master_ref = f"../{master_path.name}"
        suggested = _suggest_airspace(project_name)
        airspace = click.prompt(
            f"  Airspace ID (fleet mode detected)", default=suggested
        ).upper()[:4]

        content = _FLEET_TEMPLATE.format(
            project=project_name,
            airspace=airspace,
            master_ref=master_ref,
            language=language,
            entry_point=entry_point,
        )
    else:
        content = _SINGLE_TEMPLATE.format(
            project=project_name,
            language=language,
            entry_point=entry_point,
        )

    out_file = root / f"{project_name}.gndctrl"
    out_file.write_text(content, encoding="utf-8")

    logbook_dir = root / "logbook"
    logbook_dir.mkdir(exist_ok=True)

    return out_file, logbook_dir, fleet_mode


def init_master(root: Path, force: bool = False) -> Path:
    """Scaffold a fleet master .gndctrl in *root*."""
    out_file = root / "master.gndctrl"
    if out_file.exists() and not force:
        raise click.ClickException(
            "master.gndctrl already exists  (use --force to overwrite)"
        )

    platform_name = root.name
    out_file.write_text(
        _MASTER_TEMPLATE.format(platform=platform_name), encoding="utf-8"
    )
    return out_file
