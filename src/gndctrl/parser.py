"""
Scan source files for @gndctrl:zone and @gndctrl:node markers.
"""
import re
from pathlib import Path

from .models import InlineZoneStart, InlineZoneEnd, InlineZoneMeta, InlineNode

# Valid node id pattern: ZONE_ID.function or AIRSPACE://ZONE_ID.function
# (uppercase zone part, dot-separated function name — no spaces allowed)
_NODE_ID_RE = re.compile(
    r"^[A-Z][A-Z0-9_]*(?:://[A-Z][A-Z0-9_]*)?\.[a-zA-Z_][a-zA-Z0-9_]*$"
)

# File extensions to scan
SCANNABLE_EXTENSIONS = frozenset({
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".java", ".rb",
    ".css", ".scss", ".html", ".md", ".sh", ".yaml", ".yml",
    ".rs", ".swift", ".kt", ".php", ".c", ".cpp", ".h",
})

# Directories to always skip
SKIP_DIRS = frozenset({
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", "target", ".mypy_cache", "coverage",
    "logbook",   # logbook files are not source files
})

# Match the gndctrl marker prefix (after any comment character)
_ZONE_RE = re.compile(
    r"@gndctrl:zone\s+(START|END|meta)\s*(?:\|\s*(.+))?$",
    re.IGNORECASE,
)
_NODE_RE = re.compile(
    r"@gndctrl:node\s+(.+)$",
    re.IGNORECASE,
)


def _parse_fields(raw: str) -> dict:
    """
    Parse a pipe-delimited key=value string.

    Handles:
      - Simple values:    stability=sensitive
      - List values:      deps=[AUTH_CORE, PMT://WEBHOOK]
      - Quoted strings:   note="Not idempotent."
    """
    fields: dict = {}
    if not raw:
        return fields

    for segment in raw.split("|"):
        segment = segment.strip()
        if not segment or "=" not in segment:
            continue

        key, _, val = segment.partition("=")
        key = key.strip()
        val = val.strip()

        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            fields[key] = [v.strip() for v in inner.split(",") if v.strip()] if inner else []
        elif (val.startswith('"') and val.endswith('"')) or (
            val.startswith("'") and val.endswith("'")
        ):
            fields[key] = val[1:-1]
        else:
            fields[key] = val

    return fields


def _extract_marker(line: str) -> str | None:
    """
    Strip comment syntax and return the @gndctrl marker content,
    or None if the line contains no marker.
    """
    # Find the marker anchor — works regardless of comment style
    for prefix in ("@gndctrl:",):
        idx = line.find(prefix)
        if idx != -1:
            # Strip trailing comment closers like */ -->
            content = line[idx:].rstrip()
            for closer in ("*/", "-->"):
                if content.endswith(closer):
                    content = content[: -len(closer)].rstrip()
            return content
    return None


def scan_file(path: Path) -> list:
    """Return all gndctrl markers found in *path*, in line order."""
    markers: list = []

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except (PermissionError, IsADirectoryError, OSError):
        return markers

    file_str = str(path)

    for lineno, line in enumerate(text.splitlines(), 1):
        content = _extract_marker(line)
        if content is None:
            continue

        # ── Zone marker ───────────────────────────────────────────────────────
        m = _ZONE_RE.match(content)
        if m:
            action = m.group(1).upper()
            fields = _parse_fields(m.group(2) or "")
            zone_id = fields.get("id", "")

            if action == "START":
                markers.append(
                    InlineZoneStart(
                        id=zone_id,
                        stability=fields.get("stability"),
                        zone_type=fields.get("type", []),
                        deps=fields.get("deps", []),
                        minimum_agent_class=fields.get("minimum_agent_class"),
                        file=file_str,
                        line=lineno,
                    )
                )
            elif action == "END":
                markers.append(InlineZoneEnd(id=zone_id, file=file_str, line=lineno))
            elif action == "META":
                markers.append(
                    InlineZoneMeta(
                        id=fields.get("id", zone_id),
                        owner=fields.get("owner"),
                        doc=fields.get("doc"),
                        file=file_str,
                        line=lineno,
                    )
                )
            continue

        # ── Node marker ───────────────────────────────────────────────────────
        m = _NODE_RE.match(content)
        if m:
            fields = _parse_fields(m.group(1))
            node_id = fields.get("id", "")
            note = fields.get("note")

            # Reject markers whose id looks like prose (contains spaces or
            # doesn't match the ZONE.function / AIRSPACE://ZONE.function pattern).
            # Note-only markers (no id, just note="...") are always valid.
            # Markers with neither a valid id nor a note are skipped entirely.
            if node_id and not _NODE_ID_RE.match(node_id):
                continue  # documentation example, not a live marker
            if not node_id and not note:
                continue  # incomplete marker, skip

            markers.append(
                InlineNode(
                    id=node_id,
                    risk=fields.get("risk"),
                    touches=fields.get("touches", []),
                    crid=fields.get("crid"),
                    minimum_agent_class=fields.get("minimum_agent_class"),
                    note=note,
                    file=file_str,
                    line=lineno,
                )
            )

    return markers


def scan_directory(root: Path) -> list:
    """Recursively scan *root* for all gndctrl markers in source files."""
    all_markers: list = []

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        # Skip excluded directories
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        # Skip .gndctrl config files
        if path.name.endswith(".gndctrl"):
            continue
        # Only scan text source files
        if path.suffix not in SCANNABLE_EXTENSIONS:
            continue

        all_markers.extend(scan_file(path))

    return all_markers
