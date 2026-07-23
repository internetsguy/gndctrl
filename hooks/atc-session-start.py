#!/usr/bin/env python3
"""
gndctrl Air Traffic Control — session-start context injector (SessionStart).

Backported from the pyChisel platform hook (chisel-base/hooks/gndctrl-session.py)
and generalized for standalone installs: instead of hardcoded platform roots, it
scans from the session's working directory (from hook stdin), walking UP to find
an enclosing governed project and DOWN (bounded) to find governed subprojects.

This closes the cold-start gap: without it, an agent only discovers gndctrl when
the edit gate denies its first edit. With it, every session opens knowing which
projects are governed and what the pre-flight rule is — the tripwire becomes the
backstop instead of the introduction.

Pure stdlib, fail-open: any error emits no context and exits 0.
Disable: remove the SessionStart entry from ~/.claude/settings.json, or set
env ATC_SESSION_START_OFF=1.
"""
import sys, os, json

MAXDEPTH = 3
PRUNE_DIRS = {"node_modules", "__pycache__", ".git", ".next", "dist", "build",
              "venv", ".venv", "target", ".mypy_cache", "coverage"}


def find_docs_down(root):
    docs = []
    root = root.rstrip("/") or "/"
    base_depth = root.count(os.sep)
    for dirpath, dirnames, filenames in os.walk(root):
        if dirpath.count(os.sep) - base_depth >= MAXDEPTH:
            dirnames[:] = []
        dirnames[:] = [d for d in dirnames if d not in PRUNE_DIRS]
        for fn in filenames:
            if fn.endswith(".gndctrl"):
                docs.append(os.path.join(dirpath, fn))
    return docs


def find_docs_up(start):
    docs, d = [], start
    while True:
        try:
            docs.extend(os.path.join(d, f) for f in os.listdir(d) if f.endswith(".gndctrl"))
        except Exception:
            pass
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return docs


def main():
    try:
        if os.environ.get("ATC_SESSION_START_OFF") == "1":
            return
        try:
            data = json.load(sys.stdin)
        except Exception:
            data = {}
        cwd = data.get("cwd") or os.getcwd()

        found = sorted(set(find_docs_up(cwd)) | set(find_docs_down(cwd)))
        if not found:
            return  # ungoverned session — inject nothing, stay silent

        listing = "\n".join("  - " + p for p in found)
        ctx = (
            "⚠️ gndctrl PRE-FLIGHT (enforced by hooks):\n"
            "This session can reach gndctrl-governed projects. Before editing ANY code in "
            "one, you MUST first read that project's *.gndctrl document — its zone registry, "
            "@gndctrl:zone / @gndctrl:node markers, gotchas, and relevant logbook entries. "
            "Reading a README/TODO/notes file is NOT a substitute. Enforcement is mechanical: "
            "a PreToolUse edit gate DENIES edits until the governing .gndctrl is read this "
            "session; zones marked stability=locked cannot be auto-edited at all (human "
            "clearance only); one agent per zone at a time.\n"
            "Governed projects reachable from here:\n" + listing
        )
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": ctx,
            }
        }))
    except Exception:
        pass  # fail open — never break session start


if __name__ == "__main__":
    main()
