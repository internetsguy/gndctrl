"""
Audit checks for zone markers, CRIDs, and dependency integrity.
"""
import re
from pathlib import Path

from .models import (
    AuditViolation,
    GndctrlDocument,
    InlineZoneStart,
    InlineZoneEnd,
    InlineNode,
)
from .parser import scan_directory

# CRID regex: matches both single-mode (ZONE-YYYYMMDD-NNN) and
# fleet-mode (AIRSPACE-ZONE-YYYYMMDD-NNN)
_CRID_RE = re.compile(
    r"^([A-Z]{2,4})-(?:([A-Z]{2,4})-)?(\d{8})-(\d{3,4})$"
)

# Extract CRID prefix from a logbook filename stem.
# e.g. "CHI-AUTH-20260324-001-seed-admin-startup" → "CHI-AUTH-20260324-001"
_CRID_FROM_STEM_RE = re.compile(
    r"^([A-Z]{2,4}-(?:[A-Z]{2,4}-)?[0-9]{8}-[0-9]{3,4})"
)


def _collect_logbook_crids(logbook_dir: Path) -> set[str]:
    crids: set[str] = set()
    if not logbook_dir.is_dir():
        return crids
    for f in logbook_dir.iterdir():
        if f.is_file() and f.suffix == ".md":
            m = _CRID_FROM_STEM_RE.match(f.stem)
            if m:
                crids.add(m.group(1))
    return crids


# ── Check A1: Zone START/END pairs ────────────────────────────────────────────

def check_zone_pairs(markers: list) -> list[AuditViolation]:
    """Every @gndctrl:zone START must have a matching END in the same file."""
    violations: list[AuditViolation] = []

    # Group markers by file
    files: dict[str, list] = {}
    for m in markers:
        files.setdefault(m.file, []).append(m)

    for file_path, file_markers in files.items():
        open_zones: dict[str, InlineZoneStart] = {}

        for marker in file_markers:
            if isinstance(marker, InlineZoneStart):
                if marker.id in open_zones:
                    violations.append(
                        AuditViolation(
                            severity="error",
                            check_id="A1",
                            message=(
                                f"Zone '{marker.id}' opened again before previous START was closed"
                            ),
                            file=marker.file,
                            line=marker.line,
                        )
                    )
                open_zones[marker.id] = marker

            elif isinstance(marker, InlineZoneEnd):
                if marker.id in open_zones:
                    del open_zones[marker.id]
                else:
                    violations.append(
                        AuditViolation(
                            severity="error",
                            check_id="A1",
                            message=f"Zone END for '{marker.id}' has no matching START",
                            file=marker.file,
                            line=marker.line,
                        )
                    )

        for zone_id, start in open_zones.items():
            violations.append(
                AuditViolation(
                    severity="error",
                    check_id="A1",
                    message=f"Zone '{zone_id}' has START marker but no matching END",
                    file=start.file,
                    line=start.line,
                )
            )

    return violations


# ── Check A2: Node IDs reference valid zones ──────────────────────────────────

def check_node_ids(markers: list, doc: GndctrlDocument) -> list[AuditViolation]:
    """Every node id must reference a zone that exists in the config or inline markers."""
    violations: list[AuditViolation] = []

    # Zones known from .gndctrl
    config_zones = set(doc.zones.keys())
    # Zones found inline in source files
    inline_zones = {m.id for m in markers if isinstance(m, InlineZoneStart) if m.id}

    all_zones = config_zones | inline_zones

    for marker in markers:
        if not isinstance(marker, InlineNode):
            continue

        # note-only markers (@gndctrl:node note="...") are annotations on the
        # previous node and intentionally have no id — skip id validation
        if not marker.id:
            if marker.note:
                continue
            violations.append(
                AuditViolation(
                    severity="error",
                    check_id="A2",
                    message="Node marker missing 'id' field",
                    file=marker.file,
                    line=marker.line,
                )
            )
            continue

        if "." not in marker.id:
            violations.append(
                AuditViolation(
                    severity="error",
                    check_id="A2",
                    message=(
                        f"Node id '{marker.id}' must be ZONE_ID.function_name "
                        f"or AIRSPACE://ZONE_ID.function_name"
                    ),
                    file=marker.file,
                    line=marker.line,
                )
            )
            continue

        # Extract the zone part
        if "://" in marker.id:
            zone_part = marker.id.split("://")[1].split(".")[0]
        else:
            zone_part = marker.id.split(".")[0]

        if zone_part not in all_zones:
            violations.append(
                AuditViolation(
                    severity="error",
                    check_id="A2",
                    message=(
                        f"Node '{marker.id}' references unknown zone '{zone_part}'"
                    ),
                    file=marker.file,
                    line=marker.line,
                )
            )

    return violations


# ── Checks A3/A4: CRID format and logbook existence ───────────────────────────

def check_crids(markers: list, project_root: Path) -> list[AuditViolation]:
    """CRIDs in node markers must be well-formed and have matching logbook files."""
    violations: list[AuditViolation] = []
    logbook_crids = _collect_logbook_crids(project_root / "logbook")

    for marker in markers:
        # Skip note-only annotation markers (no id = not a trackable node)
        if not isinstance(marker, InlineNode) or not marker.crid or not marker.id:
            continue

        crid = marker.crid

        # A4: format check
        if not _CRID_RE.match(crid):
            violations.append(
                AuditViolation(
                    severity="error",
                    check_id="A4",
                    message=(
                        f"Invalid CRID format '{crid}'. "
                        f"Expected ZONE-YYYYMMDD-NNN or AIRSPACE-ZONE-YYYYMMDD-NNN"
                    ),
                    file=marker.file,
                    line=marker.line,
                )
            )
            continue

        # A3: logbook entry must exist
        if crid not in logbook_crids:
            violations.append(
                AuditViolation(
                    severity="error",
                    check_id="A3",
                    message=(
                        f"No logbook entry for CRID '{crid}'. "
                        f"Create logbook/{crid}-<description>.md"
                    ),
                    file=marker.file,
                    line=marker.line,
                )
            )

    return violations


# ── Check A6: Dependency resolution and circular deps ─────────────────────────

def check_deps(doc: GndctrlDocument) -> list[AuditViolation]:
    """Deps must reference real zones; no circular dependencies."""
    violations: list[AuditViolation] = []
    zone_ids = set(doc.zones.keys())

    # Validate each dep resolves locally (cross-airspace deps are fleet-mode, skipped here)
    for zone_id, zone in doc.zones.items():
        for dep in zone.deps:
            if "://" in dep:
                continue   # cross-airspace: fleet-mode check, not single-mode
            if dep not in zone_ids:
                violations.append(
                    AuditViolation(
                        severity="error",
                        check_id="A6",
                        message=f"Zone '{zone_id}' depends on unknown zone '{dep}'",
                    )
                )

    # Circular dependency detection via iterative DFS
    def find_cycle(start: str) -> list[str] | None:
        stack = [(start, [start])]
        visited: set[str] = set()
        while stack:
            node, path = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            zone = doc.zones.get(node)
            if not zone:
                continue
            for dep in zone.deps:
                if "://" in dep:
                    continue
                if dep == start:
                    return path + [dep]
                if dep not in visited:
                    stack.append((dep, path + [dep]))
        return None

    seen: set[str] = set()
    for zone_id in doc.zones:
        if zone_id in seen:
            continue
        cycle = find_cycle(zone_id)
        if cycle:
            seen.update(cycle)
            violations.append(
                AuditViolation(
                    severity="error",
                    check_id="A6",
                    message=f"Circular dependency: {' → '.join(cycle)}",
                )
            )

    return violations


# ── Check A9: No dependencies on deprecated zones ────────────────────────────

def check_deprecated_deps(doc: GndctrlDocument) -> list[AuditViolation]:
    violations: list[AuditViolation] = []
    for zone_id, zone in doc.zones.items():
        for dep in zone.deps:
            if "://" in dep:
                continue
            dep_zone = doc.zones.get(dep)
            if dep_zone and dep_zone.stability == "deprecated":
                violations.append(
                    AuditViolation(
                        severity="error",
                        check_id="A9",
                        message=(
                            f"Zone '{zone_id}' depends on deprecated zone '{dep}'. "
                            f"Migrate away from '{dep}' before adding new deps."
                        ),
                    )
                )
    return violations


# ── Check A10: Zone index drift (warning) ─────────────────────────────────────

def check_zone_drift(markers: list, doc: GndctrlDocument) -> list[AuditViolation]:
    """Warn if zones appear in code but not in config, or vice versa."""
    violations: list[AuditViolation] = []

    inline_zone_ids = {
        m.id.split("://")[-1] if "://" in m.id else m.id
        for m in markers
        if isinstance(m, InlineZoneStart) and m.id
    }
    config_zone_ids = set(doc.zones.keys())

    for zone_id in inline_zone_ids - config_zone_ids:
        violations.append(
            AuditViolation(
                severity="warning",
                check_id="A10",
                message=(
                    f"Zone '{zone_id}' found in inline markers but not declared in .gndctrl"
                ),
            )
        )

    for zone_id in config_zone_ids - inline_zone_ids:
        # Only warn for zones with path patterns (they should appear in code)
        zone = doc.zones.get(zone_id)
        if zone and zone.paths:
            violations.append(
                AuditViolation(
                    severity="info",
                    check_id="A10",
                    message=(
                        f"Zone '{zone_id}' declared in .gndctrl but no inline markers found"
                    ),
                )
            )

    return violations


# ── Main audit runner ─────────────────────────────────────────────────────────

def run_audit(
    project_root: Path, doc: GndctrlDocument
) -> tuple[list[AuditViolation], list]:
    """
    Run all audit checks.
    Returns (violations, all_markers).
    """
    markers = scan_directory(project_root)

    violations: list[AuditViolation] = []
    violations.extend(check_zone_pairs(markers))
    violations.extend(check_node_ids(markers, doc))
    violations.extend(check_crids(markers, project_root))
    violations.extend(check_deps(doc))
    violations.extend(check_deprecated_deps(doc))
    violations.extend(check_zone_drift(markers, doc))

    return violations, markers
