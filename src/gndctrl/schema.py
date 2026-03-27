"""
Load and validate a .gndctrl YAML document.
"""
from pathlib import Path
from typing import Optional

import yaml

from .models import GndctrlDocument, ZoneDefinition, VALID_STABILITIES, VALID_ZONE_TYPES, VALID_AGENT_CLASSES


def _as_list(val) -> list:
    if val is None:
        return []
    if isinstance(val, list):
        return val
    return [val]


def load_gndctrl(path: Path) -> tuple[Optional[GndctrlDocument], list[str]]:
    """
    Parse a .gndctrl file.  Returns (document, errors).
    If the file cannot be parsed at all, document is None.
    Schema validation errors are returned alongside a best-effort document.
    """
    errors: list[str] = []

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return None, [f"YAML parse error in {path.name}: {exc}"]
    except OSError as exc:
        return None, [f"Cannot read {path}: {exc}"]

    if not isinstance(raw, dict):
        return None, [f"{path.name} does not contain a YAML mapping"]

    # ── Zones ─────────────────────────────────────────────────────────────────
    zones: dict[str, ZoneDefinition] = {}
    raw_zones = raw.get("zones") or {}

    for zone_id, zone_data in raw_zones.items():
        if not isinstance(zone_data, dict):
            errors.append(f"Zone '{zone_id}': expected a mapping, got {type(zone_data).__name__}")
            continue

        stability = zone_data.get("stability", "active")
        if stability not in VALID_STABILITIES:
            errors.append(
                f"Zone '{zone_id}': invalid stability '{stability}'. "
                f"Must be one of: {', '.join(sorted(VALID_STABILITIES))}"
            )
            stability = "active"

        zone_types = _as_list(zone_data.get("type", ["code"]))
        for t in zone_types:
            if t not in VALID_ZONE_TYPES:
                errors.append(
                    f"Zone '{zone_id}': invalid type '{t}'. "
                    f"Must be one of: {', '.join(sorted(VALID_ZONE_TYPES))}"
                )

        mac = zone_data.get("minimum_agent_class")
        if mac and mac not in VALID_AGENT_CLASSES:
            errors.append(
                f"Zone '{zone_id}': invalid minimum_agent_class '{mac}'. "
                f"Must be one of: {', '.join(sorted(VALID_AGENT_CLASSES))}"
            )
            mac = None

        deps = _as_list(zone_data.get("deps", []))
        paths = _as_list(zone_data.get("paths", []))
        gotchas = _as_list(zone_data.get("gotchas", []))
        decisions = _as_list(zone_data.get("decisions", []))

        zones[zone_id] = ZoneDefinition(
            id=zone_id,
            stability=stability,
            zone_type=zone_types,
            deps=deps,
            minimum_agent_class=mac,
            paths=paths,
            description=str(zone_data.get("description") or ""),
            gotchas=gotchas,
            decisions=decisions,
        )

    # ── Document ──────────────────────────────────────────────────────────────
    meta = raw.get("meta") or {}
    project_name = meta.get("project") or path.stem.replace(".gndctrl", "")

    version = str(raw.get("version") or "0.1.0")
    if not version.startswith("0.1"):
        errors.append(
            f"Spec version '{version}' may be incompatible with this CLI (supports 0.1.x)"
        )

    doc = GndctrlDocument(
        airspace=raw.get("airspace") or None,
        version=version,
        master_ref=raw.get("master_ref") or None,
        project=project_name,
        zones=zones,
        raw=raw,
        source_file=str(path),
    )

    return doc, errors


def find_gndctrl_file(start: Path) -> Optional[Path]:
    """
    Walk up from *start* to find the nearest .gndctrl file.
    Prefers project documents over fleet master documents.
    """
    for directory in [start, *start.parents]:
        candidates = sorted(directory.glob("*.gndctrl"))
        if not candidates:
            continue
        if len(candidates) == 1:
            return candidates[0]
        # Prefer files that have a 'zones:' section (project docs over master docs)
        with_zones = []
        for c in candidates:
            try:
                raw = yaml.safe_load(c.read_text(encoding="utf-8"))
                if isinstance(raw, dict) and raw.get("zones"):
                    with_zones.append(c)
            except Exception:
                pass
        return with_zones[0] if with_zones else candidates[0]
    return None
