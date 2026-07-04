"""
gndctrl runtime zone-lock table (`.gndctrl.locks`).

A machine-managed JSON file at the project root (alongside `.gndctrl`) that records which
agent session currently holds which zone, so two agents never edit the same zone at once.
It is NOT part of the `.gndctrl` document — keeping volatile lock state out of the document
is what keeps the document byte-stable for prompt caching (see the spec's Cache-Stable
Documents section). The file is gitignored and safe to delete when no agent sessions are active.

Format (stable — the pChisel harness reimplements the same bytes in
chisel-base/backend/gndctrl_gate.py; keep the two in sync):

    {"zones": {"AUTH_CORE": {"pid": 4821, "provider": "codex",
                             "holder": "session-or-user-id",
                             "acquired_at": "2026-07-04T12:00:00+00:00"}}}

Liveness: a lock is held only while its holder PID is alive **in the same host / PID namespace**
that recorded it. Stale entries (dead PID, same host) are ignored on read and reclaimed on the next
acquire — a crashed agent never wedges a zone. Entries written by a *different* host (the optional
`host` field) are NOT reclaimed by a foreign reader — it cannot judge another namespace's PIDs, so
it leaves them alone rather than destroying live locks (e.g. a containerised CLI must not wipe an
in-container harness's locks). A non-positive/invalid PID is always treated as dead regardless of
host — `os.kill(0, 0)` targets the caller's own process group and would otherwise look "alive"
forever. All operations are stdlib-only and guarded by an advisory `fcntl.flock` for the
read-modify-write; every function fails safe (a malformed or unreadable file reads as empty).

Format (optional `host` added; readers tolerate its absence):

    {"zones": {"AUTH_CORE": {"pid": 4821, "host": "container-id", "provider": "codex",
                             "holder": "session-or-user-id",
                             "acquired_at": "2026-07-04T12:00:00+00:00"}}}
"""
import fcntl
import json
import os
import socket
from datetime import datetime, timezone
from pathlib import Path

LOCK_FILENAME = ".gndctrl.locks"
_HOST = socket.gethostname()


def lock_path(root) -> Path:
    return Path(root) / LOCK_FILENAME


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _pid_int(pid):
    """Parse a pid to a positive int, or None. pid <= 0 is never a valid holder: os.kill(0, 0)
    signals the caller's own process group and always 'succeeds', which would make a pid-0 lock
    immortal (e.g. a CLI run as PID 1 whose getppid() is 0)."""
    try:
        n = int(pid)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def pid_alive(pid) -> bool:
    """True if the process is alive in THIS namespace. Signal 0 only checks existence/permission.
    A non-positive/invalid pid is always dead (see _pid_int)."""
    n = _pid_int(pid)
    if n is None:
        return False
    try:
        os.kill(n, 0)
        return True
    except OSError:
        return False


def _read_raw(fh) -> dict:
    try:
        fh.seek(0)
        data = fh.read()
        parsed = json.loads(data) if data.strip() else {}
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _prune(locks: dict) -> dict:
    """Drop dead holders (stale-lock reclamation). Rules, in order:
      1. invalid/non-positive pid → always dead (drop) — never immortal;
      2. entry from a DIFFERENT host → keep (a foreign reader can't judge another namespace's
         PIDs and must not destroy its live locks);
      3. same host (or no host recorded) → keep iff the pid is alive here."""
    zones = locks.get("zones") if isinstance(locks, dict) else None
    zones = zones if isinstance(zones, dict) else {}
    live = {}
    for z, e in zones.items():
        if not isinstance(e, dict) or _pid_int(e.get("pid")) is None:
            continue
        host = e.get("host")
        if host and host != _HOST:
            live[z] = e
        elif pid_alive(e.get("pid")):
            live[z] = e
    return {"zones": live}


def read_locks(root) -> dict:
    """Return {'zones': {...}} with dead holders pruned. Never raises."""
    p = lock_path(root)
    if not p.exists():
        return {"zones": {}}
    try:
        with open(p, "r", encoding="utf-8") as fh:
            fcntl.flock(fh, fcntl.LOCK_SH)
            try:
                raw = _read_raw(fh)
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)
        return _prune(raw)
    except Exception:
        return {"zones": {}}


def _mutate(root, fn):
    """Exclusive read-modify-write: prune dead holders, apply fn(locks) (mutating `locks`
    in place and returning a result), persist deterministically, return the result.
    Never raises — on any error returns fn's documented failure value via the caller."""
    p = lock_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a+", encoding="utf-8") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            locks = _prune(_read_raw(fh))
            result = fn(locks)
            fh.seek(0)
            fh.truncate()
            json.dump(locks, fh, indent=2, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
            return result
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def acquire(root, zone, pid, provider="", holder=""):
    """Try to take the zone lock. Returns (True, None) on success (or re-entrant same-pid),
    or (False, holder_entry) when a DIFFERENT live pid holds it."""
    pid = int(pid)

    def fn(locks):
        zones = locks.setdefault("zones", {})
        cur = zones.get(zone)
        if cur and pid_alive(cur.get("pid")) and int(cur.get("pid")) != pid:
            return (False, cur)
        zones[zone] = {"pid": pid, "host": _HOST, "provider": provider,
                       "holder": holder, "acquired_at": _now()}
        return (True, None)

    return _mutate(root, fn)


def release(root, zone, pid) -> bool:
    """Release the zone lock IF held by this pid. Returns True if a lock was removed."""
    pid = int(pid)

    def fn(locks):
        zones = locks.get("zones", {})
        cur = zones.get(zone)
        if cur and int(cur.get("pid", -1)) == pid:
            del zones[zone]
            return True
        return False

    return _mutate(root, fn)


def release_all_for_pid(root, pid) -> list:
    """Release every zone held by this pid (turn cleanup). Returns the zone ids released."""
    pid = int(pid)

    def fn(locks):
        zones = locks.get("zones", {})
        removed = [z for z, e in list(zones.items()) if int(e.get("pid", -1)) == pid]
        for z in removed:
            del zones[z]
        return removed

    return _mutate(root, fn)


def list_locks(root) -> dict:
    """Live zone → holder-entry map (dead holders already pruned)."""
    return read_locks(root).get("zones", {})


def check(root, zone):
    """Live holder entry for `zone`, or None if free."""
    return read_locks(root).get("zones", {}).get(zone)
