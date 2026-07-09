# gndctrl hooks — Claude Code integration

Mechanical enforcement of gndctrl governance, so "read the governing document before
you act" stops being prose nobody follows and becomes a tripwire that self-corrects.

These are [Claude Code](https://claude.com/claude-code) `PreToolUse` hooks. They deny a
tool call with a reason; the agent reads the named document, then retries. The user is
never prompted.

## The ops-action gate (`gndctrl-ops-gate.py`)

gndctrl's edit-preflight gates **edits** to governed files. But the actions that take a
platform *down* are **commands** — a service restart, a DNS reload, a container recreate.
Those are otherwise ungated. This hook closes that gap: when a Bash command matches a
governed **ops hazard**, it blocks until the hazard's governing document has been read in
the current session.

It is **data-driven** — the hook contains no platform-specific rules. It reads a hazard
registry; you describe your platform's dangerous commands there and never touch the hook.

### Install

1. Copy the hook somewhere stable (e.g. `~/.claude/hooks/gndctrl-ops-gate.py`).
2. Copy `gndctrl-ops-hazards.sample.json` to `~/.claude/gndctrl-ops-hazards.json` and
   replace the examples with your own hazards (or point `GNDCTRL_OPS_HAZARDS` at any path).
3. Register it in `~/.claude/settings.json`:

   ```json
   {
     "hooks": {
       "PreToolUse": [
         {
           "matcher": "Bash",
           "hooks": [
             { "type": "command", "command": "python3 ~/.claude/hooks/gndctrl-ops-gate.py" }
           ]
         }
       ]
     }
   }
   ```

### Hazard registry

Each hazard entry:

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

### Behaviour

- **Fail-open** on any internal error, a missing/malformed registry, or an unverifiable
  transcript — a hook bug must never brick the shell.
- **Fail-closed** only on the deterministic case: the command matches a hazard *and* its
  doc has not been read this session.
- **Escape hatch:** `GNDCTRL_OPS_GATE_OFF=1` disables the gate for a command you're sure of.

## The edit preflight (`gndctrl-preflight.py`)

The companion hook (see the main gndctrl docs) gates **edits** to any file inside a
gndctrl-governed project until that project's `*.gndctrl` document has been read. The
ops-gate is its operational sibling: edits and commands, both governed.
