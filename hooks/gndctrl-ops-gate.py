#!/usr/bin/env python3
"""
gndctrl ops-action gate (PreToolUse: Bash).

The preflight tripwire gates EDITS to governed files. But the actions that take a
platform DOWN are COMMANDS — a service restart, a DNS reload, a container recreate.
Those are otherwise ungated: an agent can run a documented-dangerous command with a
cross-zone side effect and never read the hazard. (Seen in the wild: a routine
service-restart command changed a core container's internal IP and locked every
tenant out — the hazard was documented in the right zone, but *running the command*
surfaced nothing, because edits are gated and commands are not. This closes that gap.)

This hook makes ops hazards mechanical, mirroring the edit gate: when a Bash command
matches a governed hazard, it DENIES until the governing document has been Read this
session. The agent reads the hazard, understands the blast radius + recovery, then
retries. The user is never prompted.

DATA-DRIVEN — the hook has NO platform-specific rules. It reads a hazard registry
(GNDCTRL_OPS_HAZARDS env, else ~/.claude/gndctrl-ops-hazards.json). Each hazard:
    {"id","pattern"(regex on the command),"doc"(file to read),"severity","reason"}
Add/adjust hazards by editing that file — never this code. That's what makes the
gate portable to any platform installing gndctrl.

Fail-OPEN on any internal error (never brick the shell because of a hook bug).
Fail-CLOSED only on the deterministic "this command is a known hazard and you have
not read its doc this session."

Disable: set GNDCTRL_OPS_GATE_OFF=1, or remove the Bash PreToolUse entry from
~/.claude/settings.json.
"""
import sys, os, json, re, glob


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


def _registry_paths():
    env = os.environ.get("GNDCTRL_OPS_HAZARDS")
    if env:
        yield env
    yield os.path.expanduser("~/.claude/gndctrl-ops-hazards.json")


def _load_hazards():
    for p in _registry_paths():
        try:
            if p and os.path.exists(p):
                with open(p) as f:
                    return json.load(f).get("hazards", [])
        except Exception:
            return []  # malformed registry → fail open (no gating)
    return []


def _doc_read_this_session(transcript_path: str, doc: str) -> bool:
    """True if the transcript shows a Read tool call touching `doc` (by abs path or
    basename) — same session-read heuristic as the edit preflight."""
    if not transcript_path or not os.path.exists(transcript_path):
        return True  # can't verify → fail open (don't block on missing transcript)
    doc_abs = os.path.abspath(doc)
    doc_base = os.path.basename(doc)
    try:
        with open(transcript_path, errors="ignore") as f:
            for line in f:
                if doc_base not in line:
                    continue
                if '"Read"' not in line and "'Read'" not in line:
                    continue
                if doc_abs in line or doc_base in line:
                    return True
    except Exception:
        return True  # fail open on transcript read error
    return False


def main():
    if os.environ.get("GNDCTRL_OPS_GATE_OFF") == "1":
        allow()
    try:
        data = json.load(sys.stdin)
    except Exception:
        allow()
    if data.get("tool_name") != "Bash":
        allow()
    command = (data.get("tool_input") or {}).get("command") or ""
    if not command:
        allow()

    hazards = _load_hazards()
    if not hazards:
        allow()

    transcript = data.get("transcript_path") or ""
    for hz in hazards:
        pattern = hz.get("pattern")
        doc = hz.get("doc")
        if not pattern or not doc:
            continue
        try:
            if not re.search(pattern, command):
                continue
        except re.error:
            continue  # bad regex in registry → skip that hazard, don't block
        if _doc_read_this_session(transcript, doc):
            continue  # already read the hazard doc this session → allow
        sev = hz.get("severity", "high")
        reason = hz.get("reason", "")
        deny(
            f"⛔ gndctrl ops-gate — this command is a governed hazard (severity: {sev}).\n"
            f"Before running it, read the governing document so you know the blast radius "
            f"and recovery:\n    {doc}\n"
            + (f"\n{reason}\n" if reason else "")
            + "\nGrep/Read the relevant zone (not the whole file), then retry the command. "
            "This gate exists because the most dangerous actions on this platform are "
            "commands, not edits — and a documented hazard is worthless if nobody reads it "
            "before acting. (Override for one command only if you're certain: "
            "GNDCTRL_OPS_GATE_OFF=1.)"
        )
    allow()


if __name__ == "__main__":
    main()
