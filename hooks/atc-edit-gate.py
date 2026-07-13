#!/usr/bin/env python3
"""
gndctrl Air Traffic Control — edit gate (PreToolUse: Edit|Write|NotebookEdit).

Blocks an edit to any file inside a gndctrl-governed project until that
project's *.gndctrl document has actually been Read in the current session.

This is the headline enforcement of gndctrl: "act first, read the governing
document last" is the #1 recurring agent failure. Prose in a CLAUDE.md / AGENTS.md
gets skipped — this hook makes the rule mechanical and self-correcting: it DENIES
the edit with a reason, the agent reads the .gndctrl zone, then retries. The user
is never prompted.

It is the edit half of Air Traffic Control; its sibling `atc-ops-gate.py` gates
dangerous COMMANDS the same way. Edits and commands, both cleared before takeoff.

Fail-OPEN on any internal error (never brick editing because of a hook bug).
Fail-CLOSED only on the deterministic "you didn't read it" case.

Disable: remove the PreToolUse entry from ~/.claude/settings.json, or set
env ATC_EDIT_GATE_OFF=1.
"""
import sys, os, json, glob


def allow():
    sys.exit(0)


def deny(reason: str):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def main():
    if os.environ.get("ATC_EDIT_GATE_OFF") == "1":
        allow()

    try:
        data = json.load(sys.stdin)
    except Exception:
        allow()  # fail open

    if data.get("tool_name") not in ("Edit", "Write", "NotebookEdit"):
        allow()

    ti = data.get("tool_input") or {}
    fp = ti.get("file_path") or ti.get("notebook_path") or ""
    if not fp:
        allow()
    fp = os.path.abspath(fp)

    # Walk up to the nearest ancestor dir that holds a *.gndctrl doc.
    d = os.path.dirname(fp)
    govern_dir = None
    docs = []
    while True:
        docs = sorted(glob.glob(os.path.join(d, "*.gndctrl")))
        if docs:
            govern_dir = d
            break
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent

    if not govern_dir:
        allow()  # not a gndctrl-governed project

    # Editing a .gndctrl file itself is always fine (you're maintaining it).
    if fp in (os.path.abspath(x) for x in docs):
        allow()

    # Prefer the project doc named after the dir (e.g. my-app.gndctrl);
    # but reading ANY .gndctrl in the governing dir satisfies the gate.
    preferred = os.path.join(govern_dir, os.path.basename(govern_dir) + ".gndctrl")
    if preferred not in docs:
        preferred = docs[0]

    # Did this session Read any governing .gndctrl? Inspect the transcript.
    tp = data.get("transcript_path") or ""
    read_any = False
    if tp and os.path.exists(tp):
        doc_abs = set(os.path.abspath(x) for x in docs)
        doc_base = set(os.path.basename(x) for x in docs)
        try:
            with open(tp, errors="ignore") as f:
                for line in f:
                    # Cheap pre-filter, then PROVE it's a genuine Read tool_use whose
                    # file_path IS the .gndctrl — not a mere co-occurrence of "Read" +
                    # the filename in prose / injected context (that false-satisfied the gate).
                    if ".gndctrl" not in line or "Read" not in line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    msg = obj.get("message", obj) if isinstance(obj, dict) else {}
                    content = msg.get("content") if isinstance(msg, dict) else None
                    if not isinstance(content, list):
                        continue
                    for b in content:
                        if not (isinstance(b, dict) and b.get("type") == "tool_use"
                                and b.get("name") == "Read"):
                            continue
                        fp2 = str((b.get("input") or {}).get("file_path", ""))
                        if os.path.abspath(fp2) in doc_abs or os.path.basename(fp2) in doc_base:
                            read_any = True
                            break
                    if read_any:
                        break
        except Exception:
            allow()  # fail open on transcript read error

    if read_any:
        allow()

    deny(
        "⛔ gndctrl Air Traffic Control — edit not cleared.\n"
        f"Before editing {os.path.relpath(fp, govern_dir)} you must read the part of the "
        f"governing project document that covers it:\n    {preferred}\n"
        "Read the RELEVANT section, not the whole file: read the zone registry to find which "
        "zone owns this file, then that zone's @gndctrl markers / gotchas / logbook. For a "
        "large doc, Grep it to locate the zone and Read just that range — do NOT page the "
        "entire document. A targeted, partial Read satisfies this gate. Then retry this edit. "
        "(Reading the governing document before you touch its code is the whole point of "
        "gndctrl — editing first is the #1 recurring failure.)"
    )


if __name__ == "__main__":
    main()
