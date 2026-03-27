"""
Pre-flight zone clearance check.
"""
from .models import GndctrlDocument, ZoneDefinition, AGENT_CLASS_RANK, STABILITY_RULES


def _agent_cleared(zone: ZoneDefinition, agent_class: str) -> tuple[bool, str]:
    """Returns (cleared, denial_reason)."""
    required = zone.minimum_agent_class
    if not required:
        return True, ""
    agent_rank = AGENT_CLASS_RANK.get(agent_class.lower(), 2)
    required_rank = AGENT_CLASS_RANK.get(required.lower(), 0)
    if agent_rank < required_rank:
        return False, (
            f"zone requires {required.upper()} class; "
            f"your agent is {agent_class.upper()}"
        )
    return True, ""


def _resolve_dep_chain(
    zone_id: str, doc: GndctrlDocument, visited: set | None = None
) -> list[ZoneDefinition]:
    """Return all transitive local deps of zone_id (cross-airspace deps skipped)."""
    if visited is None:
        visited = set()
    if zone_id in visited:
        return []
    visited.add(zone_id)

    zone = doc.zones.get(zone_id)
    if not zone:
        return []

    chain = []
    for dep in zone.deps:
        if "://" in dep:
            continue
        dep_zone = doc.zones.get(dep)
        if dep_zone:
            chain.append(dep_zone)
            chain.extend(_resolve_dep_chain(dep, doc, visited))
    return chain


def run_preflight(
    doc: GndctrlDocument, zone_ids: list[str], agent_class: str
) -> dict:
    """
    Generate a pre-flight clearance brief for the given zones.

    Returns a dict with:
      - agent_class, project, airspace
      - cleared_zones: list of zone dicts with clearance details
      - blocked_zones: list of zone dicts with denial reasons
      - dep_warnings: notes about the dependency chain
    """
    result = {
        "agent_class": agent_class,
        "project": doc.project,
        "airspace": doc.airspace or "single mode",
        "cleared_zones": [],
        "blocked_zones": [],
        "not_found": [],
        "dep_warnings": [],
    }

    for zone_id in zone_ids:
        # Strip airspace prefix if provided (e.g. CHI://AUTH_CORE → AUTH_CORE)
        local_id = zone_id.split("://")[-1] if "://" in zone_id else zone_id
        zone = doc.zones.get(local_id)

        if not zone:
            result["not_found"].append(zone_id)
            continue

        cleared, reason = _agent_cleared(zone, agent_class)

        entry = {
            "id": local_id,
            "stability": zone.stability,
            "type": zone.zone_type,
            "minimum_agent_class": zone.minimum_agent_class,
            "cleared": cleared,
            "block_reason": reason,
            "stability_rule": STABILITY_RULES.get(zone.stability, ""),
            "deps": zone.deps,
            "description": zone.description,
            "gotchas": zone.gotchas,
            "decisions": zone.decisions,
        }

        if cleared:
            result["cleared_zones"].append(entry)
        else:
            result["blocked_zones"].append(entry)

        # For sensitive/locked zones, resolve and surface the dep chain
        if zone.stability in ("sensitive", "locked"):
            dep_chain = _resolve_dep_chain(local_id, doc)
            for dep_zone in dep_chain:
                result["dep_warnings"].append(
                    f"Dep chain: {dep_zone.id} (stability={dep_zone.stability})"
                )
                dep_cleared, dep_reason = _agent_cleared(dep_zone, agent_class)
                if not dep_cleared:
                    result["dep_warnings"].append(
                        f"  ↳ Also blocked: {dep_reason}"
                    )

    return result
