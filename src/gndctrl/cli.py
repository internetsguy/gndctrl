"""
gndctrl CLI — Ground Control for your codebase.
"""
import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()

STABILITY_COLOURS = {
    "locked":       "red",
    "sensitive":    "yellow",
    "stable":       "green",
    "active":       "cyan",
    "experimental": "dim",
    "deprecated":   "red",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _find_gndctrl(start: Path) -> Path | None:
    from .schema import find_gndctrl_file
    return find_gndctrl_file(start)


def _load_or_exit(path: Path) -> "GndctrlDocument":
    from .schema import load_gndctrl
    doc, errors = load_gndctrl(path)
    for e in errors:
        console.print(f"  [yellow]![/yellow] {e}")
    if doc is None:
        console.print(f"  [red]✗[/red] Cannot continue — fix the errors above.")
        sys.exit(1)
    return doc


# ── CLI group ─────────────────────────────────────────────────────────────────

@click.group()
@click.version_option("0.1.0", prog_name="gndctrl")
def main():
    """gndctrl — Ground Control for your codebase.

    Zone-based governance and enforcement for AI agents.
    """
    pass


# ── gndctrl init ──────────────────────────────────────────────────────────────

@main.command()
@click.argument("path", default=".", type=click.Path(file_okay=False, path_type=Path))
@click.option("--force", is_flag=True, help="Overwrite existing .gndctrl")
@click.option("--master", is_flag=True, help="Scaffold a fleet master .gndctrl instead")
def init(path, force, master):
    """Scaffold .gndctrl and logbook/ in the current project.

    Detects single vs fleet mode automatically.
    Use --master to create a fleet master document.

    \b
    Examples:
      gndctrl init
      gndctrl init ./my-service
      gndctrl init --master
    """
    from .init_cmd import init_project, init_master

    root = path.resolve()
    console.print(f"\n  [bold]gndctrl init[/bold]")
    console.print("  " + "─" * 38 + "\n")

    try:
        if master:
            out_file = init_master(root, force=force)
            console.print(f"  [green]✓[/green] Created [bold]{out_file.name}[/bold] (fleet master)")
        else:
            out_file, logbook_dir, fleet_mode = init_project(root, force=force)
            mode = "[cyan]fleet[/cyan]" if fleet_mode else "[green]single[/green]"
            console.print(f"  [green]✓[/green] Created [bold]{out_file.name}[/bold] (mode: {mode})")
            console.print(f"  [green]✓[/green] Created [bold]logbook/[/bold]")
    except click.ClickException as e:
        console.print(f"  [red]✗[/red] {e.format_message()}")
        sys.exit(1)

    console.print(f"\n  [bold]Next steps:[/bold]")
    console.print(f"    1. Edit [bold]{out_file.name}[/bold] — define your real zones")
    console.print(f"    2. Add markers to source files:")
    console.print(f"       [dim]# @gndctrl:zone START | id=MY_ZONE | stability=active | type=[code][/dim]")
    console.print(f"       [dim]# @gndctrl:zone END   | id=MY_ZONE[/dim]")
    console.print(f"    3. Run [bold]gndctrl audit[/bold] to validate\n")


# ── gndctrl audit ─────────────────────────────────────────────────────────────

@main.command()
@click.argument("path", default=".", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text",
              help="Output format")
@click.option("--strict", is_flag=True, help="Exit 1 on warnings too (not just errors)")
def audit(path, fmt, strict):
    """Validate zone markers, CRIDs, and dependency integrity.

    Runs all checks and reports violations. Exits 0 if clean, 1 if errors found.

    \b
    Checks:
      A1  Zone START/END pairs match
      A2  Node IDs reference valid zones
      A3  CRIDs have matching logbook entries
      A4  CRID format is valid
      A6  Dependency resolution + circular dep detection
      A9  No dependencies on deprecated zones
      A10 Zone index drift (config vs code)

    \b
    Examples:
      gndctrl audit
      gndctrl audit ./my-service --format json
    """
    from .auditor import run_audit

    project_root = path.resolve()
    gndctrl_file = _find_gndctrl(project_root)

    if fmt == "text":
        console.print(f"\n  [bold]gndctrl audit[/bold]")
        console.print("  " + "─" * 38)
        console.print(f"  Scanning [dim]{project_root}[/dim]...\n")

    if not gndctrl_file:
        msg = "No .gndctrl file found. Run `gndctrl init` first."
        if fmt == "json":
            click.echo(json.dumps({"error": msg}))
        else:
            console.print(f"  [red]✗[/red] {msg}")
        sys.exit(1)

    doc = _load_or_exit(gndctrl_file)

    if fmt == "text":
        airspace_str = f"airspace: {doc.airspace}" if doc.airspace else "single mode"
        console.print(
            f"  [green]✓[/green] Loaded [bold]{gndctrl_file.name}[/bold] "
            f"({airspace_str}, {len(doc.zones)} zones)"
        )

    violations, markers = run_audit(project_root, doc)

    errors   = [v for v in violations if v.severity == "error"]
    warnings = [v for v in violations if v.severity == "warning"]
    infos    = [v for v in violations if v.severity == "info"]

    zone_starts = [m for m in markers if hasattr(m, "stability")]
    nodes       = [m for m in markers if hasattr(m, "risk")]
    files_hit   = len({m.file for m in markers})

    if fmt == "json":
        click.echo(json.dumps({
            "project":          doc.project,
            "airspace":         doc.airspace,
            "zones_in_config":  len(doc.zones),
            "files_with_markers": files_hit,
            "markers_found":    len(markers),
            "violations": [
                {
                    "severity": v.severity,
                    "check":    v.check_id,
                    "message":  v.message,
                    "file":     v.file,
                    "line":     v.line,
                }
                for v in violations
            ],
        }, indent=2))
        sys.exit(1 if errors or (strict and warnings) else 0)

    # ── Text output ───────────────────────────────────────────────────────────
    if violations:
        console.print(f"\n  [bold]VIOLATIONS ({len(violations)})[/bold]")
        console.print("  " + "━" * 48)

        for v in violations:
            colour = {"error": "red", "warning": "yellow", "info": "dim"}.get(
                v.severity, "white"
            )
            loc = f"  [dim]{v.file}:{v.line}[/dim]" if v.file else ""
            console.print(
                f"\n  [{colour}][{v.severity.upper()}][/{colour}] "
                f"[dim]{v.check_id}[/dim]{loc}"
            )
            console.print(f"  {v.message}")

    # ── Summary ───────────────────────────────────────────────────────────────
    console.print(f"\n  [bold]SUMMARY[/bold]")
    console.print("  " + "━" * 48)
    from .models import InlineZoneEnd
    zone_ends = [m for m in markers if isinstance(m, InlineZoneEnd)]
    console.print(f"  Zones (config):    {len(doc.zones)}")
    console.print(f"  Zone markers:      {len(zone_starts)} opens, {len(zone_ends)} closes")
    console.print(f"  Node markers:      {len(nodes)}")
    console.print(f"  Files with markers:{files_hit}")

    if errors:
        console.print(f"  [red bold]Errors:            {len(errors)}[/red bold]")
    if warnings:
        console.print(f"  [yellow]Warnings:          {len(warnings)}[/yellow]")
    if infos:
        console.print(f"  [dim]Info:              {len(infos)}[/dim]")

    if not violations:
        console.print(f"\n  [green bold]✓ Clean — no violations found[/green bold]\n")
    elif not errors:
        console.print(f"\n  [yellow]⚠ Warnings only — audit passed[/yellow]\n")
    else:
        console.print(f"\n  [red]✗ Audit failed — fix errors above[/red]\n")

    sys.exit(1 if errors or (strict and warnings) else 0)


# ── gndctrl preflight ─────────────────────────────────────────────────────────

@main.command()
@click.argument("zones", nargs=-1)
@click.option("--agent-class", "-a", default="medium",
              type=click.Choice(["ultralight", "light", "medium", "heavy", "super"]),
              help="Your agent's weight class (default: medium)")
@click.option("--path", "-p", default=".",
              type=click.Path(exists=True, file_okay=False, path_type=Path))
def preflight(zones, agent_class, path):
    """Run pre-flight zone check before starting a task.

    Lists available zones if no ZONE arguments given.

    \b
    Examples:
      gndctrl preflight                          # list all zones
      gndctrl preflight AUTH_CORE                # check one zone
      gndctrl preflight AUTH_CORE PAYMENT -a heavy
    """
    from .preflight import run_preflight

    project_root = path.resolve()
    gndctrl_file = _find_gndctrl(project_root)

    if not gndctrl_file:
        console.print("  [red]✗[/red] No .gndctrl file found. Run `gndctrl init` first.")
        sys.exit(1)

    doc = _load_or_exit(gndctrl_file)

    # No zones given — show zone index
    if not zones:
        console.print(f"\n  [bold]Zones in {doc.project}[/bold]  "
                      f"[dim]({doc.airspace or 'single mode'})[/dim]\n")
        for zone_id, zone in doc.zones.items():
            colour = STABILITY_COLOURS.get(zone.stability, "white")
            mac = f"[dim]min:{zone.minimum_agent_class}[/dim]" if zone.minimum_agent_class else ""
            desc = (zone.description[:55] + "…") if len(zone.description) > 55 else zone.description
            console.print(
                f"  [{colour}]■[/{colour}] [bold]{zone_id:<22}[/bold] "
                f"[{colour}]{zone.stability:<12}[/{colour}] {mac}  [dim]{desc}[/dim]"
            )
        console.print(
            f"\n  Usage: [bold]gndctrl preflight ZONE_ID [ZONE_ID ...] "
            f"--agent-class medium[/bold]\n"
        )
        return

    brief = run_preflight(doc, list(zones), agent_class)

    console.print(f"\n  [bold]GNDCTRL PRE-FLIGHT[/bold]")
    console.print("  " + "━" * 48)
    console.print(f"  Project:      {doc.project}")
    console.print(f"  Airspace:     {brief['airspace']}")
    console.print(f"  Agent class:  [bold]{agent_class.upper()}[/bold]")
    console.print()

    # Not found
    for zone_id in brief["not_found"]:
        console.print(f"  [red]✗ NOT FOUND[/red]  '{zone_id}' — run `gndctrl preflight` to list zones")

    # Blocked
    for zone in brief["blocked_zones"]:
        colour = STABILITY_COLOURS.get(zone["stability"], "white")
        console.print(
            f"  [red]✗ DENIED[/red]    [bold]{zone['id']}[/bold]  "
            f"[{colour}]{zone['stability']}[/{colour}]"
        )
        console.print(f"    {zone['block_reason']}")

    # Cleared
    if brief["cleared_zones"]:
        console.print(f"  [green bold]CLEARANCE BRIEF[/green bold]")
        console.print("  " + "─" * 44)

        for zone in brief["cleared_zones"]:
            colour = STABILITY_COLOURS.get(zone["stability"], "white")
            console.print(
                f"\n  [green]✓[/green] [bold]{zone['id']}[/bold]  "
                f"[{colour}]{zone['stability']}[/{colour}]"
            )

            if zone["description"]:
                console.print(f"    {zone['description']}")

            console.print(f"    [dim]Rule: {zone['stability_rule']}[/dim]")

            if zone["gotchas"]:
                console.print(f"    [yellow]Gotchas:[/yellow]")
                for g in zone["gotchas"]:
                    console.print(f"      • {g}")

            if zone["decisions"]:
                console.print(f"    [dim]Decisions:[/dim]")
                for d in zone["decisions"]:
                    console.print(f"      • {d}")

            if zone["deps"]:
                console.print(f"    [dim]Deps: {', '.join(zone['deps'])}[/dim]")

    # Dep chain warnings
    if brief["dep_warnings"]:
        console.print(f"\n  [yellow]DEP CHAIN NOTES[/yellow]")
        for w in brief["dep_warnings"]:
            console.print(f"    {w}")

    # Final verdict
    console.print()
    if brief["blocked_zones"] or brief["not_found"]:
        console.print(
            f"  [red]✗ BLOCKED[/red] — resolve the above before proceeding\n"
        )
        sys.exit(1)
    else:
        console.print(
            f"  [green bold]✓ GREEN LIGHT[/green bold] — "
            f"proceed within authorised zone scope\n"
        )


# ── gndctrl zones (quick listing) ─────────────────────────────────────────────

@main.command(name="zones")
@click.argument("path", default=".", type=click.Path(exists=True, file_okay=False, path_type=Path))
def list_zones(path):
    """List all zones defined in the nearest .gndctrl file."""
    project_root = path.resolve()
    gndctrl_file = _find_gndctrl(project_root)

    if not gndctrl_file:
        console.print("  [red]✗[/red] No .gndctrl file found.")
        sys.exit(1)

    doc = _load_or_exit(gndctrl_file)

    table = Table(show_header=True, header_style="bold dim", box=None, pad_edge=False)
    table.add_column("Zone", min_width=20)
    table.add_column("Stability", min_width=13)
    table.add_column("Type", min_width=15)
    table.add_column("Min Class", min_width=10)
    table.add_column("Deps")

    for zone_id, zone in doc.zones.items():
        colour = STABILITY_COLOURS.get(zone.stability, "white")
        table.add_row(
            f"[bold]{zone_id}[/bold]",
            f"[{colour}]{zone.stability}[/{colour}]",
            ", ".join(zone.zone_type),
            zone.minimum_agent_class or "—",
            ", ".join(zone.deps) or "—",
        )

    console.print()
    console.print(f"  [bold]{doc.project}[/bold]  [dim]{doc.airspace or 'single mode'}[/dim]\n")
    console.print(table)
    console.print()
