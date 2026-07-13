#!/usr/bin/env bash
set -e

REPO="https://github.com/internetsguy/gndctrl.git"
RAW="https://raw.githubusercontent.com/internetsguy/gndctrl/master"
MIN_PYTHON="3.9"
CLAUDE_DIR="${HOME}/.claude"
HOOK_DIR="${CLAUDE_DIR}/hooks"

# ── Colour helpers ────────────────────────────────────────────────────────────
red()   { printf '\033[0;31m%s\033[0m\n' "$*"; }
green() { printf '\033[0;32m%s\033[0m\n' "$*"; }
dim()   { printf '\033[2m%s\033[0m\n'   "$*"; }

echo ""
echo "  gndctrl installer"
echo "  ─────────────────────────────────────────"

# ── Python check ──────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    red "  ✗ Python 3.9+ is required but not found"
    echo "    Install Python from https://python.org and try again."
    exit 1
fi

PYVER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYMINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
PYMAJOR=$(python3 -c "import sys; print(sys.version_info.major)")

if [ "$PYMAJOR" -lt 3 ] || { [ "$PYMAJOR" -eq 3 ] && [ "$PYMINOR" -lt 9 ]; }; then
    red "  ✗ Python $MIN_PYTHON+ required (found $PYVER)"
    exit 1
fi

dim "  Python $PYVER ✓"

# ── pip check ─────────────────────────────────────────────────────────────────
if ! python3 -m pip --version &>/dev/null; then
    red "  ✗ pip not found. Install pip and try again."
    exit 1
fi

# ── Install ───────────────────────────────────────────────────────────────────
echo "  Installing gndctrl from GitHub..."
echo ""

python3 -m pip install --quiet "git+${REPO}"

green "  ✓ gndctrl CLI installed"
echo ""

# ── Air Traffic Control — enforcement hooks ───────────────────────────────────
# The CLI is passive (init / audit / report). ATC is the enforcement layer: two
# Claude Code PreToolUse hooks that DENY an edit / dangerous command until the
# governing .gndctrl has been read this session. This is what makes gndctrl
# mechanical instead of prose nobody follows — so install it, not just the CLI.
echo "  Installing Air Traffic Control enforcement hooks..."

if ! command -v curl &>/dev/null; then
    red "  ✗ curl is required to fetch the ATC hooks"
    echo "    Install curl and re-run, or install the hooks manually (see hooks/README.md)."
    exit 1
fi

mkdir -p "$HOOK_DIR"

fetch() {  # fetch <remote-path> <local-dest>
    if ! curl -fsSL "${RAW}/$1" -o "$2"; then
        red "  ✗ failed to download $1"
        exit 1
    fi
}

fetch "hooks/atc-edit-gate.py" "${HOOK_DIR}/atc-edit-gate.py"
fetch "hooks/atc-ops-gate.py"  "${HOOK_DIR}/atc-ops-gate.py"
chmod +x "${HOOK_DIR}/atc-edit-gate.py" "${HOOK_DIR}/atc-ops-gate.py"
dim "  Hooks → ${HOOK_DIR}/atc-{edit,ops}-gate.py ✓"

# Seed the ops-hazard registry only if the user doesn't already have one.
HAZARDS="${CLAUDE_DIR}/atc-ops-hazards.json"
if [ ! -f "$HAZARDS" ]; then
    fetch "hooks/atc-ops-hazards.sample.json" "$HAZARDS"
    dim "  Ops-hazard registry seeded → ${HAZARDS} (edit it with YOUR dangerous commands)"
else
    dim "  Ops-hazard registry already present → ${HAZARDS} (left untouched)"
fi

# Wire both gates into ~/.claude/settings.json — idempotent, preserves existing config.
SETTINGS="${CLAUDE_DIR}/settings.json"
[ -f "$SETTINGS" ] && cp "$SETTINGS" "${SETTINGS}.bak"
SETTINGS="$SETTINGS" python3 - <<'PY'
import json, os
p = os.environ["SETTINGS"]
os.makedirs(os.path.dirname(p), exist_ok=True)
try:
    with open(p) as f:
        cfg = json.load(f)
    if not isinstance(cfg, dict):
        cfg = {}
except Exception:
    cfg = {}

pre = cfg.setdefault("hooks", {}).setdefault("PreToolUse", [])
if not isinstance(pre, list):
    cfg["hooks"]["PreToolUse"] = pre = []

def present(basename):
    for entry in pre:
        for h in (entry.get("hooks") or []):
            if basename in (h.get("command") or ""):
                return True
    return False

def add(matcher, cmd):
    for entry in pre:
        if entry.get("matcher") == matcher:
            entry.setdefault("hooks", []).append({"type": "command", "command": cmd})
            return
    pre.append({"matcher": matcher, "hooks": [{"type": "command", "command": cmd}]})

added = []
if not present("atc-edit-gate.py"):
    add("Edit|Write|NotebookEdit", "python3 ~/.claude/hooks/atc-edit-gate.py")
    added.append("edit gate")
if not present("atc-ops-gate.py"):
    add("Bash", "python3 ~/.claude/hooks/atc-ops-gate.py")
    added.append("ops gate")

if added:
    with open(p, "w") as f:
        json.dump(cfg, f, indent=2)
    print("  Wired into settings.json: " + ", ".join(added))
else:
    print("  settings.json already wires both ATC gates — left unchanged")
PY

echo ""
green "  ✓ gndctrl + Air Traffic Control installed"
echo ""
echo "  Enforcement is now live in new Claude Code sessions:"
echo "    • edit gate — blocks edits to a governed project until its .gndctrl is read"
echo "    • ops gate  — blocks a hazardous command until its governing doc is read"
echo "    Tune hazards in ~/.claude/atc-ops-hazards.json"
echo ""
echo "  Quick start:"
echo "    gndctrl init          # scaffold .gndctrl in current project"
echo "    gndctrl audit         # validate all zone markers"
echo "    gndctrl preflight     # list zones and run pre-flight check"
echo "    gndctrl --help        # full command reference"
echo ""
