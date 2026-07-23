#!/usr/bin/env python3
"""
gndctrl Air Traffic Control — ops gate (PreToolUse: Bash).

The edit gate (`atc-edit-gate.py`) clears EDITS to governed files. But the actions
that take a platform DOWN are COMMANDS — a service restart, a DNS reload, a container
recreate. Those are otherwise ungated: an agent can run a documented-dangerous command
with a cross-zone side effect and never read the hazard. (Seen in the wild: a routine
service-restart command changed a core container's internal IP and locked every tenant
out — the hazard was documented in the right zone, but *running the command* surfaced
nothing, because edits are gated and commands are not. This closes that gap.)

This hook makes ops hazards mechanical, mirroring the edit gate: when a Bash command
matches a governed hazard, it DENIES until the governing document has been Read this
session. The agent reads the hazard, understands the blast radius + recovery, then
retries. The user is never prompted. Together the two gates are Air Traffic Control:
edits and commands, both cleared before takeoff.

DATA-DRIVEN — the hook has NO platform-specific rules. It reads a hazard registry
(ATC_OPS_HAZARDS env, else ~/.claude/atc-ops-hazards.json). Each hazard:
    {"id","pattern"(regex on the command),"doc"(file to read),"severity","reason"}
Add/adjust hazards by editing that file — never this code. That's what makes the
gate portable to any platform installing gndctrl.

Fail-OPEN on any internal error (never brick the shell because of a hook bug).
Fail-CLOSED only on the deterministic "this command is a known hazard and you have
not read its doc this session."

Disable: set ATC_OPS_GATE_OFF=1, or remove the Bash PreToolUse entry from
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
    env = os.environ.get("ATC_OPS_HAZARDS")
    if env:
        yield env
    yield os.path.expanduser("~/.claude/atc-ops-hazards.json")


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
    """True iff the transcript holds a GENUINE Read tool_use whose file_path is `doc`
    (abs path or basename match) — NOT a mere co-occurrence of 'Read' + the filename in
    prose, injected context, or this gate's own prior deny message (the substring version
    of this check false-satisfied after one denial, because the deny reason itself contains
    the doc path). Same proof as the edit gate — keep the two in sync."""
    if not transcript_path or not os.path.exists(transcript_path):
        return True  # can't verify → fail open (don't block on missing transcript)
    doc_abs = os.path.abspath(doc)
    doc_base = os.path.basename(doc)
    try:
        with open(transcript_path, errors="ignore") as f:
            for line in f:
                if doc_base not in line or "Read" not in line:
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
                    if os.path.abspath(fp2) == doc_abs or os.path.basename(fp2) == doc_base:
                        return True
    except Exception:
        return True  # fail open on transcript read error
    return False


def main():
    if os.environ.get("ATC_OPS_GATE_OFF") == "1":
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
            f"⛔ gndctrl Air Traffic Control — ops command not cleared (severity: {sev}).\n"
            f"This command is a governed hazard. Before running it, read the governing "
            f"document so you know the blast radius and recovery:\n    {doc}\n"
            + (f"\n{reason}\n" if reason else "")
            + "\nGrep/Read the relevant zone (not the whole file), then retry the command. "
            "This gate exists because the most dangerous actions on a platform are commands, "
            "not edits — and a documented hazard is worthless if nobody reads it before "
            "acting. (Override for one command only if you're certain: ATC_OPS_GATE_OFF=1.)"
        )
    allow()


if __name__ == "__main__":
    main()
