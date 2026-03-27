#!/usr/bin/env bash
set -e

REPO="https://github.com/internetsguy/gndctrl.git"
MIN_PYTHON="3.9"

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

echo ""
green "  ✓ gndctrl installed"
echo ""
echo "  Quick start:"
echo "    gndctrl init          # scaffold .gndctrl in current project"
echo "    gndctrl audit         # validate all zone markers"
echo "    gndctrl preflight     # list zones and run pre-flight check"
echo "    gndctrl --help        # full command reference"
echo ""
