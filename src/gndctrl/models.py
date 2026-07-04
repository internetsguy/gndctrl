import fnmatch
from dataclasses import dataclass, field
from typing import Optional


def zone_for_path(doc, relpath):
    """Return the id of the first zone whose `paths[]` patterns match `relpath`, else None.

    `paths[]` entries are glob patterns (e.g. "backend/routes/*.py", "src/billing/*"). A path
    matches if it fnmatches the pattern, equals it, or falls under a directory-style pattern
    (pattern treated as a prefix: "src/billing" matches "src/billing/webhook.py"). First match
    wins in zone-declaration order — deterministic and enough for lock resolution; inline
    @gndctrl:zone markers (which can override path patterns per file) are not consulted here.
    """
    rel = str(relpath).strip().lstrip("./")
    if not rel:
        return None
    for zid, zone in getattr(doc, "zones", {}).items():
        for pat in (getattr(zone, "paths", None) or []):
            pat = str(pat).strip().lstrip("./")
            if not pat:
                continue
            if (rel == pat
                    or fnmatch.fnmatch(rel, pat)
                    or fnmatch.fnmatch(rel, pat.rstrip("/") + "/*")):
                return zid
    return None


# ── Inline marker objects (from scanning source files) ────────────────────────

@dataclass
class InlineZoneStart:
    id: str
    stability: Optional[str] = None
    zone_type: list = field(default_factory=list)
    deps: list = field(default_factory=list)
    minimum_agent_class: Optional[str] = None
    file: str = ""
    line: int = 0


@dataclass
class InlineZoneEnd:
    id: str
    file: str = ""
    line: int = 0


@dataclass
class InlineZoneMeta:
    id: str
    owner: Optional[str] = None
    doc: Optional[str] = None
    file: str = ""
    line: int = 0


@dataclass
class InlineNode:
    id: str
    risk: Optional[str] = None
    touches: list = field(default_factory=list)
    crid: Optional[str] = None
    minimum_agent_class: Optional[str] = None
    note: Optional[str] = None
    file: str = ""
    line: int = 0


# ── .gndctrl document objects ─────────────────────────────────────────────────

@dataclass
class ZoneDefinition:
    id: str
    stability: str
    zone_type: list
    deps: list
    minimum_agent_class: Optional[str]
    paths: list
    description: str = ""
    gotchas: list = field(default_factory=list)
    decisions: list = field(default_factory=list)


@dataclass
class GndctrlDocument:
    airspace: Optional[str]
    version: str
    master_ref: Optional[str]
    project: str
    zones: dict        # zone_id -> ZoneDefinition
    raw: dict          # raw parsed YAML
    source_file: str = ""


# ── Audit results ─────────────────────────────────────────────────────────────

@dataclass
class AuditViolation:
    severity: str      # "error" | "warning" | "info"
    check_id: str
    message: str
    file: Optional[str] = None
    line: Optional[int] = None


# ── Constants ─────────────────────────────────────────────────────────────────

VALID_STABILITIES = frozenset(
    {"deprecated", "experimental", "active", "stable", "sensitive", "locked"}
)

VALID_ZONE_TYPES = frozenset({"code", "design", "data", "config", "docs"})

VALID_AGENT_CLASSES = frozenset({"ultralight", "light", "medium", "heavy", "super"})

AGENT_CLASS_RANK = {
    "ultralight": 0,
    "light": 1,
    "medium": 2,
    "heavy": 3,
    "super": 4,
}

STABILITY_RULES = {
    "locked":       "Do NOT modify. Surface proposed change as diff for human review only.",
    "sensitive":    "Read full zone doc + all dep chain docs. Surface risk summary before proceeding.",
    "stable":       "Read zone doc before any structural changes. Flag cross-zone edits to user.",
    "active":       "Normal development. Verify deps not broken. No cross-zone restrictions.",
    "experimental": "Act freely. No dep check required.",
    "deprecated":   "Flag for removal. Do not extend. Refuse new dependencies — suggest migration path.",
}
