# Air Traffic Control — gndctrl's read-before-act clearance gates

**Air Traffic Control (ATC)** is gndctrl's clearance layer: the pieces that require an
agent to get clearance — read the governing document — *before it acts*. It's one part of
gndctrl's broader enforcement (which also includes the dispatch gate and zone locks), not
the whole of it. ATC's job is narrow and mechanical: "read the governing document before
you act" stops being prose nobody follows and becomes a tripwire that self-corrects.

These are [Claude Code](https://claude.com/claude-code) `PreToolUse` hooks. They deny a
tool call with a reason; the agent reads the named document, then retries. The user is
never prompted. There are two deny gates — edits and commands — plus a session-start injector that
announces governance when a session opens:

| Hook | File | Event · what it does |
|---|---|---|
| **Edit gate** | `atc-edit-gate.py` | `PreToolUse` · denies any `Edit`/`Write`/`NotebookEdit` inside a gndctrl-governed project until its `.gndctrl` is read; v2 also enforces locked zones, zone locks, and class floors |
| **Ops gate** | `atc-ops-gate.py` | `PreToolUse` · denies any `Bash` command matching a governed **ops hazard** until its doc is read |
| **Session-start** | `atc-session-start.py` | `SessionStart` · announces governed projects + the pre-flight rule at session open (injects context, never denies) |

`install.sh` installs and wires both gates automatically. The sections below document
what each does and how to configure it; you only touch this by hand if you want to
customize.

---

## The edit gate (`atc-edit-gate.py`) — v2, zone-aware

v1 gated one thing: no edit inside a governed project until the governing `*.gndctrl`
was Read this session. v2 keeps that and adds zone-level enforcement, backported from
the reference platform's dispatch gate. Checks run in order; first deny wins:

1. **Locked zone.** The edited file resolves to a zone with `stability: locked` →
   deny, always. Reading the doc does not clear it; locked means human clearance only.
   The deny message instructs the agent to present its change as a diff and stop.
2. **Zone lock.** A *different* live agent holds the file's zone in `.gndctrl.locks` →
   deny, naming the holder. Your own lock (matching session id, or a holder PID that is
   an ancestor of the hook process) passes. Locks from a different host are always
   respected — the hook can't judge another machine's PIDs. Stale locks (dead PID, same
   host) are ignored, so a crashed agent never wedges a zone.
3. **Weight class.** The zone declares `minimum_agent_class` AND the environment
   declares `GNDCTRL_AGENT_CLASS` below it → deny. Class is **declared, never
   inferred**: if the env var is unset, no class check runs. Set it per session or per
   provider (`GNDCTRL_AGENT_CLASS=heavy`).
4. **Doc-read.** The v1 gate, unchanged: deny until the governing `*.gndctrl` has been
   genuinely Read this session (verified as an actual `Read` tool_use in the transcript,
   not a mention of the filename in prose). The deny message now names the resolved zone
   and its stability so the agent can Grep straight to the right section.

**How the file resolves to a zone:** the hook parses the project `.gndctrl` zone
registry and matches the file against each zone's `paths[]` patterns. When more than one
zone matches (a broad `"*"` catch-all and a specific `"legal/*"` locked zone), the
**most restrictive stability wins** — a locked file never slips through because a
permissive zone matched first.

**Degradation ladder (all fail-open):** zone parsing needs PyYAML. If PyYAML is missing,
the doc is malformed, or the registry is empty, checks 1–3 skip and check 4 still runs —
the hook never needs more than the stdlib to do its base job. Any internal error anywhere
allows the edit: a hook bug must never brick editing. The gate fails **closed** only on
the deterministic cases: locked zone, live foreign lock, declared class below floor, doc
not read.

Disable: `ATC_EDIT_GATE_OFF=1`, or remove the PreToolUse entry from
`~/.claude/settings.json`.

## The ops gate (`atc-ops-gate.py`)

The edit gate clears **edits**; but the actions that take a platform *down* are
**commands** — a service restart, a DNS reload, a container recreate. Those are otherwise
ungated. This hook closes that gap: when a Bash command matches a governed **ops hazard**,
it blocks until the hazard's governing document has been read in the current session.

It is **data-driven** — the hook contains no platform-specific rules. It reads a hazard
registry; you describe your platform's dangerous commands there and never touch the hook.

### Hazard registry

`install.sh` seeds `~/.claude/atc-ops-hazards.json` from `atc-ops-hazards.sample.json`.
Edit that file (or point `ATC_OPS_HAZARDS` at any path) and replace the examples with your
own hazards. Each entry:

| field | meaning |
|---|---|
| `id` | short identifier |
| `pattern` | Python regex matched against the full command string |
| `doc` | the governing document that must be read this session before the command runs |
| `severity` | free-form label surfaced in the deny message (`outage`, `catastrophic`, …) |
| `reason` | one or two sentences: the blast radius and the safe alternative/recovery |

Guidance: gate the **raw dangerous command**, not a safe wrapper (gate `docker restart
core-app`, not the health-checked deploy script that supersedes it). Point `doc` at the
zone that actually documents the hazard, so reading it teaches the recovery.

- **Fail-open** on any internal error, a missing/malformed registry, or an unverifiable
  transcript. **Fail-closed** only on the deterministic case: the command matches a hazard
  *and* its doc has not been read this session.
- **Escape hatch:** `ATC_OPS_GATE_OFF=1` disables the gate for a command you're sure of.

### Investigation tripwires

The ops gate's hazards don't have to be commands. A hazard whose `pattern` matches a
**path** fires on any Bash command that touches that path — `grep`, `cat`, `ls`,
`sqlite3`, anything — which turns the ops gate into a *read-before-you-diagnose* gate:

```json
{
  "id": "billing-investigate",
  "pattern": "/srv/myapp/billing/",
  "doc": "/srv/myapp/myapp.gndctrl",
  "severity": "info",
  "reason": "Read the BILLING zone registry entry before inspecting or asserting anything about this code. One read satisfies the whole session."
}
```

This pattern earned its place after a real incident: an agent spent hours of raw
grep/sqlite spelunking on a billing problem, re-deriving from scratch what the billing
zone's gotchas already said. Edits were gated; *investigation* wasn't — so the documented
knowledge was never loaded. An `info`-severity path tripwire closes that gap: the first
command that wanders into the zone gets denied once, the agent reads the zone doc, and
every subsequent command flows freely.

Use `severity: info` for these (they're guidance loads, not outage risks) and scope the
`pattern` to the zone's directory, not the whole project — the goal is one forced read
of the right section, not friction on everything.

## The session-start injector (`atc-session-start.py`)

A `SessionStart` hook that closes the cold-start gap: without it, an agent only
discovers gndctrl when the edit gate denies its first edit. With it, every session opens
already knowing which projects are governed and what the rules are — the tripwires
become the backstop instead of the introduction.

At session open it scans from the session's working directory — **up** to find an
enclosing governed project, and **down** (3 levels, common junk dirs pruned) to find
governed subprojects — and injects a context block listing every reachable `*.gndctrl`
plus the three standing rules: read the governing doc before editing, locked zones are
human-clearance only, one agent per zone at a time.

In an ungoverned directory it injects nothing and stays silent. Pure stdlib, fail-open.
Disable: `ATC_SESSION_START_OFF=1`, or remove the SessionStart entry from
`~/.claude/settings.json`.

---

## Install

The recommended path is the repo installer, which copies both hooks, seeds the hazard
registry, and merges the `PreToolUse` entries into `~/.claude/settings.json` idempotently:

```bash
curl -fsSL https://raw.githubusercontent.com/internetsguy/gndctrl/master/install.sh | bash
```

> **Upgrading from v1 — one intentional behavior change.** The edit gate now enforces
> **locked zones**: an agent can no longer edit a `stability: locked` zone even after
> reading the governing doc (human clearance only). It also respects zone locks and, when
> `GNDCTRL_AGENT_CLASS` is set, per-zone class floors. If an upgrade suddenly starts
> denying an edit that v1 allowed, that is the feature v1 was missing — not a regression.

### Manual install

If you'd rather wire it yourself:

1. Copy the hooks somewhere stable, e.g. `~/.claude/hooks/atc-edit-gate.py`,
   `~/.claude/hooks/atc-ops-gate.py`, and `~/.claude/hooks/atc-session-start.py`.
2. (Ops gate only) copy `atc-ops-hazards.sample.json` to `~/.claude/atc-ops-hazards.json`
   and replace the examples with your own hazards.
3. Register both in `~/.claude/settings.json`:

   ```json
   {
     "hooks": {
       "PreToolUse": [
         {
           "matcher": "Edit|Write|NotebookEdit",
           "hooks": [
             { "type": "command", "command": "python3 ~/.claude/hooks/atc-edit-gate.py" }
           ]
         },
         {
           "matcher": "Bash",
           "hooks": [
             { "type": "command", "command": "python3 ~/.claude/hooks/atc-ops-gate.py" }
           ]
         }
       ],
       "SessionStart": [
         {
           "hooks": [
             { "type": "command", "command": "python3 ~/.claude/hooks/atc-session-start.py" }
           ]
         }
       ]
     }
   }
   ```
