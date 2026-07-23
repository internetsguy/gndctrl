#!/usr/bin/env python3
"""
gndctrl Air Traffic Control — edit gate v2 (PreToolUse: Edit|Write|NotebookEdit).

v1 gated one thing: no edit inside a governed project until the governing *.gndctrl
was Read this session. v2 keeps that and backports the harness-level enforcement
(pyChisel dispatch gate, chisel-base/backend/gndctrl_gate.py) into the standalone
hook, so a plain Claude Code install gets zone-level governance without a dispatch
harness. Checks run in this order — first deny wins:

  1. LOCKED ZONE      stability=locked → deny ALWAYS. Human clearance required;
                      reading the doc does not clear it. (Spec tier 5.)
  2. ZONE LOCK        a DIFFERENT live agent holds this zone in .gndctrl.locks →
                      deny. Our own lock (holder session_id match, or holder pid
                      is an ancestor of this hook) allows. (Spec: one agent per
                      zone.) Byte format mirrors gndctrl/src/gndctrl/lockfile.py
                      AND chisel-base/backend/gndctrl_gate.py — keep all three in sync.
  3. WEIGHT CLASS     zone declares minimum_agent_class AND env GNDCTRL_AGENT_CLASS
                      is set below it → deny. Class is DECLARED, never inferred
                      (harness-level-enforcement design note); unset env = no check.
  4. DOC READ         governing *.gndctrl not Read this session → deny (v1 gate,
                      with the proven tool_use transcript check).

Zone resolution mirrors the production gate: parse the project .gndctrl zones
registry (YAML), match the edited file against each zone's paths[] patterns,
MOST RESTRICTIVE stability wins on multi-match — a locked file must never slip
through because a permissive catch-all matched first.

Degradation ladder (all fail-open):
  - PyYAML missing / doc malformed / no zones → checks 1-3 skip, check 4 still runs
    (v1 behavior — the hook never requires more than the stdlib to do its base job).
  - Any internal error anywhere → allow. A hook bug must never brick editing.
  - Fail-CLOSED only on deterministic cases: locked zone, live foreign lock,
    declared class below floor, doc not read.

Disable: remove the PreToolUse entry from ~/.claude/settings.json, or set
env ATC_EDIT_GATE_OFF=1.
"""
import sys, os, json, glob, fnmatch, subprocess

LOCK_FILENAME = ".gndctrl.locks"

# Most-restrictive-wins ranking. Keep in sync with gndctrl/src/gndctrl/models.py
# and chisel-base/backend/gndctrl_gate.py.
_STABILITY_RANK = {"deprecated": 0, "experimental": 1, "active": 2,
                   "stable": 3, "sensitive": 4, "locked": 5}

# Keep in sync with gndctrl/src/gndctrl/models.py AGENT_CLASS_RANK.
_AGENT_CLASS_RANK = {"ultralight": 0, "light": 1, "medium": 2, "heavy": 3, "super": 4}


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


# ── Zone registry (fail-open: {} on any problem) ──────────────────────────────

def load_zones(govern_dir, docs):
    """{zone_id: {'stability','minimum_agent_class','paths':[...]}} from the first
    doc in govern_dir with a NON-EMPTY zones dict (an un-renamed init stub ships
    `zones: {}` and sorts first — binding to it would disable zone checks silently)."""
    try:
        import yaml
    except Exception:
        return {}
    try:
        for c in docs:
            try:
                with open(c, encoding="utf-8") as f:
                    raw = yaml.safe_load(f)
            except Exception:
                continue
            if isinstance(raw, dict) and isinstance(raw.get("zones"), dict) and raw["zones"]:
                out = {}
                for zid, z in raw["zones"].items():
                    if not isinstance(z, dict):
                        continue
                    paths = [str(p).strip() for p in (z.get("paths") or []) if str(p).strip()]
                    out[zid] = {
                        "stability": str(z.get("stability", "active")).lower(),
                        "minimum_agent_class": (str(z["minimum_agent_class"]).lower()
                                                if z.get("minimum_agent_class") else None),
                        "paths": paths,
                    }
                return out
        return {}
    except Exception:
        return {}


def zone_for_file(zones, relfile):
    """Most restrictive matching zone id, or None. Mirrors production _zone_for_file."""
    try:
        rel = str(relfile).strip().lstrip("./")
        best, best_rank = None, -1
        for zid, z in zones.items():
            for pat in z["paths"]:
                pat = pat.lstrip("./")
                if rel == pat or fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(rel, pat.rstrip("/") + "/*"):
                    rank = _STABILITY_RANK.get(z["stability"], 2)
                    if rank > best_rank:
                        best, best_rank = zid, rank
                    break
        return best
    except Exception:
        return None


# ── .gndctrl.locks (read-only here; format mirrors lockfile.py) ───────────────

def _pid_alive(pid) -> bool:
    try:
        n = int(pid)
    except (TypeError, ValueError):
        return False
    if n <= 0:
        return False  # os.kill(0,0) hits our own process group — pid<=0 is never a holder
    try:
        os.kill(n, 0)
        return True
    except OSError:
        return False


def _ancestor_pids():
    """PIDs from this hook up to init — a lock held by an ancestor (the Claude Code
    process that spawned us) is OUR lock. /proc on Linux, ps fallback elsewhere;
    empty set on failure (fail-open handled by caller)."""
    out, pid, hops = set(), os.getpid(), 0
    try:
        while pid > 1 and hops < 32:
            out.add(pid)
            try:
                with open(f"/proc/{pid}/stat") as f:
                    pid = int(f.read().split(")")[-1].split()[1])
            except Exception:
                r = subprocess.run(["ps", "-o", "ppid=", "-p", str(pid)],
                                   capture_output=True, text=True, timeout=2)
                pid = int(r.stdout.strip() or 0)
            hops += 1
        out.add(pid)
    except Exception:
        pass
    return out


def foreign_lock_holder(govern_dir, zone, session_id):
    """The live lock entry for `zone` held by someone OTHER than this session/process
    tree, or None. Read-only, shared-lock, fail-open (None on any error)."""
    try:
        import fcntl, socket
        p = os.path.join(govern_dir, LOCK_FILENAME)
        if not os.path.exists(p):
            return None
        with open(p, encoding="utf-8") as fh:
            fcntl.flock(fh, fcntl.LOCK_SH)
            try:
                raw = json.load(fh)
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)
        e = (raw.get("zones") or {}).get(zone)
        if not isinstance(e, dict):
            return None
        host = e.get("host")
        if host and host != socket.gethostname():
            return e  # foreign host: can't judge its PIDs, must respect the lock
        if not _pid_alive(e.get("pid")):
            return None  # stale — lockfile.py reclaims it on next mutate
        if session_id and e.get("holder") and e["holder"] == session_id:
            return None  # ours by session id
        if int(e.get("pid", -1)) in _ancestor_pids():
            return None  # ours by process ancestry
        return e
    except Exception:
        return None


# ── Transcript proof of Read (v1 logic, unchanged — the proven check) ─────────

def doc_read_this_session(transcript_path, docs):
    """True iff the transcript holds a GENUINE Read tool_use whose file_path is one
    of `docs` — not a mere co-occurrence of 'Read' + the filename in prose or an
    injected deny message (that false-satisfied the substring version of this gate).
    Keep in sync with atc-ops-gate.py:_doc_read_this_session."""
    if not transcript_path or not os.path.exists(transcript_path):
        return False
    doc_abs = set(os.path.abspath(x) for x in docs)
    doc_base = set(os.path.basename(x) for x in docs)
    try:
        with open(transcript_path, errors="ignore") as f:
            for line in f:
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
                        return True
        return False
    except Exception:
        return True  # fail open on transcript read error


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if os.environ.get("ATC_EDIT_GATE_OFF") == "1":
        allow()

    try:
        data = json.load(sys.stdin)
    except Exception:
        allow()

    if data.get("tool_name") not in ("Edit", "Write", "NotebookEdit"):
        allow()

    ti = data.get("tool_input") or {}
    fp = ti.get("file_path") or ti.get("notebook_path") or ""
    if not fp:
        allow()
    fp = os.path.abspath(fp)

    # Nearest ancestor dir holding a *.gndctrl doc.
    d = os.path.dirname(fp)
    govern_dir, docs = None, []
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
        allow()

    # Maintaining a .gndctrl doc itself is always allowed.
    if fp in (os.path.abspath(x) for x in docs):
        allow()

    relfile = os.path.relpath(fp, govern_dir)
    zones = load_zones(govern_dir, docs)
    zid = zone_for_file(zones, relfile) if zones else None
    z = zones.get(zid) if zid else None

    # ── 1. Locked zone: hard deny, always ─────────────────────────────────────
    if z and z["stability"] == "locked":
        deny(
            f"⛔ gndctrl Air Traffic Control — {relfile} is in zone {zid}, stability=locked "
            f"(prohibited airspace).\n"
            f"Locked zones require HUMAN clearance — reading the doc does not clear them and "
            f"no agent may auto-edit here. Do not retry this edit. Instead: present your "
            f"proposed change to the user as a diff and wait for them to apply it themselves, "
            f"or ask them to lower the zone's stability in the project's .gndctrl if it no "
            f"longer needs protection."
        )

    # ── 2. Zone concurrency lock ──────────────────────────────────────────────
    if zid:
        holder = foreign_lock_holder(govern_dir, zid, data.get("session_id") or "")
        if holder:
            deny(
                f"⛔ gndctrl Air Traffic Control — zone {zid} is locked by another agent "
                f"({holder.get('provider') or 'unknown provider'}, pid {holder.get('pid')}, "
                f"since {holder.get('acquired_at')}).\n"
                f"gndctrl allows one agent per zone at a time so agents don't make conflicting "
                f"edits. Work on a different zone, or wait and retry — a crashed holder's lock "
                f"self-heals via PID liveness."
            )

    # ── 3. Weight class (declared, never inferred) ────────────────────────────
    if z and z["minimum_agent_class"]:
        declared = os.environ.get("GNDCTRL_AGENT_CLASS", "").lower()
        if declared in _AGENT_CLASS_RANK:
            if _AGENT_CLASS_RANK[declared] < _AGENT_CLASS_RANK.get(z["minimum_agent_class"], 0):
                deny(
                    f"⛔ gndctrl Air Traffic Control — zone {zid} requires agent class "
                    f"{z['minimum_agent_class'].upper()}; this session is declared "
                    f"{declared.upper()} (GNDCTRL_AGENT_CLASS).\n"
                    f"Do not retry. Tell the user this task needs a heavier agent for this zone."
                )

    # ── 4. Doc-read gate (v1) ─────────────────────────────────────────────────
    if doc_read_this_session(data.get("transcript_path") or "", docs):
        allow()

    preferred = os.path.join(govern_dir, os.path.basename(govern_dir) + ".gndctrl")
    if preferred not in docs:
        preferred = docs[0]
    zone_hint = f" It is governed by zone {zid} ({z['stability']})." if z else ""
    deny(
        "⛔ gndctrl Air Traffic Control — edit not cleared.\n"
        f"Before editing {relfile} you must read the part of the governing project document "
        f"that covers it:\n    {preferred}\n{zone_hint}\n"
        "Read the RELEVANT section, not the whole file: read the zone registry to find which "
        "zone owns this file, then that zone's @gndctrl markers / gotchas / logbook. For a "
        "large doc, Grep it to locate the zone and Read just that range — do NOT page the "
        "entire document. A targeted, partial Read satisfies this gate. Then retry this edit. "
        "(Reading the governing document before you touch its code is the whole point of "
        "gndctrl — editing first is the #1 recurring failure.)"
    )


if __name__ == "__main__":
    main()
