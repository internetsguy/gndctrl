# Air Traffic Control — gndctrl's read-before-act clearance gates

**Air Traffic Control (ATC)** is gndctrl's clearance layer: the pieces that require an
agent to get clearance — read the governing document — *before it acts*. It's one part of
gndctrl's broader enforcement (which also includes the dispatch gate and zone locks), not
the whole of it. ATC's job is narrow and mechanical: "read the governing document before
you act" stops being prose nobody follows and becomes a tripwire that self-corrects.

These are [Claude Code](https://claude.com/claude-code) `PreToolUse` hooks. They deny a
tool call with a reason; the agent reads the named document, then retries. The user is
never prompted. There are two gates — edits and commands, both cleared before takeoff:

| Gate | File | Denies until you've read the governing doc, for… |
|---|---|---|
| **Edit gate** | `atc-edit-gate.py` | any `Edit`/`Write`/`NotebookEdit` to a file inside a gndctrl-governed project |
| **Ops gate** | `atc-ops-gate.py` | any `Bash` command matching a governed **ops hazard** |

`install.sh` installs and wires both gates automatically. The sections below document
what each does and how to configure it; you only touch this by hand if you want to
customize.

---

## The edit gate (`atc-edit-gate.py`)

The headline enforcement. It walks up from the file being edited to the nearest ancestor
holding a `*.gndctrl` document; if that project's `.gndctrl` has **not** been Read in the
current session, the edit is denied with a pointer to the governing doc. Reading the
`.gndctrl` (even a targeted, partial Read of the relevant zone) clears the gate.

- **Zero config** — it's data-driven off the `*.gndctrl` files already in your repos.
  No per-platform rules, no registry.
- **Fail-open** on any internal error or unverifiable transcript — a hook bug must never
  brick editing. **Fail-closed** only on the deterministic "you didn't read it" case.
- **Editing a `.gndctrl` file itself is always allowed** (you're maintaining it).
- **Escape hatch:** `ATC_EDIT_GATE_OFF=1` disables the gate for a command you're sure of.

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

---

## Install

The recommended path is the repo installer, which copies both hooks, seeds the hazard
registry, and merges the `PreToolUse` entries into `~/.claude/settings.json` idempotently:

```bash
curl -fsSL https://raw.githubusercontent.com/internetsguy/gndctrl/master/install.sh | bash
```

### Manual install

If you'd rather wire it yourself:

1. Copy the hooks somewhere stable, e.g. `~/.claude/hooks/atc-edit-gate.py` and
   `~/.claude/hooks/atc-ops-gate.py`.
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
       ]
     }
   }
   ```
