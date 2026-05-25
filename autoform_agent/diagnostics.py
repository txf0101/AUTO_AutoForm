"""Diagnostics, log discovery and environment snapshot helpers.

The diagnostic layer collects evidence for support and future development.  It
keeps default behavior read-only and uses dry-run plans for bundle creation so a
caller can review paths before copying logs.
"""

from __future__ import annotations

import json
import platform
import re
import sys
from pathlib import Path

from .commands import list_command_specs
from .coverage import module_coverage_matrix
from .paths import AutoFormInstallation, discover_installations, get_default_installation


LOG_EXTENSIONS = {".log", ".txt", ".out", ".err"}
GUI_TIMESTAMP_RE = re.compile(r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})")
GUI_OPEN_RE = re.compile(r"#FILE_LOG#Open: (?P<path>.+)$")
GUI_FILE_VERSION_RE = re.compile(
    r"Opening file \(version: (?P<version>\d+) created with revision: (?P<created_revision>\d+) "
    r"last saved with revision: (?P<last_saved_revision>[^)]+)\)"
)
GUI_JOB_STATUS_RE = re.compile(r"JobStatus string can not be loaded from '(?P<path>.+)'\.")


def collect_recent_autoform_logs(
    search_roots: list[Path] | None = None,
    install: AutoFormInstallation | None = None,
    limit: int = 50,
    preview_bytes: int = 2048,
) -> list[dict]:
    """Return recent AutoForm-like log files without copying them."""

    roots = [path.resolve() for path in search_roots] if search_roots else _default_log_roots(install)
    seen: set[str] = set()
    logs: list[dict] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or not _looks_like_log(path):
                continue
            key = str(path.resolve()).casefold()
            if key in seen:
                continue
            seen.add(key)
            stat = path.stat()
            logs.append(
                {
                    "name": path.name,
                    "path": str(path),
                    "size_bytes": stat.st_size,
                    "last_modified": stat.st_mtime,
                    "preview": _read_preview(path, preview_bytes),
                }
            )
    logs.sort(key=lambda item: item["last_modified"], reverse=True)
    return logs[:limit]


def diagnostic_bundle_plan(
    output_dir: Path,
    search_roots: list[Path] | None = None,
    limit: int = 50,
    dry_run: bool = True,
) -> dict:
    """Plan a diagnostic bundle made from recent log files."""

    logs = collect_recent_autoform_logs(search_roots=search_roots, limit=limit)
    destination = output_dir.resolve()
    planned_files = []
    for index, item in enumerate(logs, 1):
        source = Path(item["path"])
        planned_files.append(
            {
                "source": str(source),
                "destination": str(destination / f"{index:03d}_{source.name}"),
                "size_bytes": item["size_bytes"],
            }
        )
    manifest = {
        "destination": str(destination),
        "dry_run": dry_run,
        "log_count": len(planned_files),
        "planned_files": planned_files,
    }
    if not dry_run:
        destination.mkdir(parents=True, exist_ok=True)
        for item in planned_files:
            source = Path(item["source"])
            target = Path(item["destination"])
            target.write_bytes(source.read_bytes())
        (destination / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def collect_gui_project_events(
    log_dir: Path | None = None,
    limit: int = 50,
) -> list[dict]:
    """Parse AutoForm GUI logs for project open events and file facts."""

    root = log_dir.resolve() if log_dir is not None else _default_gui_log_dir()
    if not root.exists():
        return []
    events: list[dict] = []
    for log_path in sorted(root.glob("log_AFFormingUI_*.txt"), key=lambda item: item.stat().st_mtime, reverse=True):
        events.extend(_parse_gui_log(log_path))
    events.sort(key=lambda item: item.get("timestamp") or "", reverse=True)
    return events[:limit]


def environment_snapshot(
    output_path: Path | None = None,
    write: bool = False,
) -> dict:
    """Return or write a compact AutoForm Agent environment snapshot."""

    installs = [install.as_dict() for install in discover_installations()]
    snapshot = {
        "python": sys.executable,
        "python_version": sys.version,
        "platform": platform.platform(),
        "installations": installs,
        "command_specs": list_command_specs() if installs else [],
        "module_coverage": module_coverage_matrix() if installs else [],
    }
    if write:
        if output_path is None:
            raise ValueError("output_path is required when write=True")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        snapshot["written_to"] = str(output_path.resolve())
    return snapshot


def _default_log_roots(install: AutoFormInstallation | None = None) -> list[Path]:
    """Return likely log locations for the selected AutoForm installation."""
    selected = install or get_default_installation()
    return [
        selected.autoform_program_data,
        Path.cwd(),
    ]


def _looks_like_log(path: Path) -> bool:
    """Identify AutoForm logs by filename prefix and text suffix."""
    suffix = path.suffix.lower()
    if suffix not in LOG_EXTENSIONS:
        return False
    name = path.name.casefold()
    return suffix in {".log", ".out", ".err"} or "log" in name


def _read_preview(path: Path, preview_bytes: int) -> str:
    """Read a bounded log preview for diagnostics output."""
    if preview_bytes <= 0:
        return ""
    data = path.read_bytes()[:preview_bytes]
    return data.decode("utf-8", errors="replace")


def _default_gui_log_dir() -> Path:
    """Return the default GUI log folder for AutoForm R13 on Windows."""
    return Path.home() / "AppData" / "Local" / "AutoForm" / "AFplus" / "R13F" / "log"


def _parse_gui_log(log_path: Path) -> list[dict]:
    """Extract project-open records and related file facts from one GUI log."""
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    events: list[dict] = []
    current: dict | None = None
    current_timestamp: str | None = None
    for line in lines:
        timestamp_match = GUI_TIMESTAMP_RE.search(line)
        if timestamp_match:
            current_timestamp = timestamp_match.group("timestamp")
        open_match = GUI_OPEN_RE.search(line)
        if open_match:
            current = {
                "timestamp": current_timestamp,
                "event": "open_project",
                "path": open_match.group("path"),
                "log_path": str(log_path),
                "file_version": None,
                "created_revision": None,
                "last_saved_revision": None,
                "job_status_available": None,
            }
            events.append(current)
            continue
        version_match = GUI_FILE_VERSION_RE.search(line)
        if version_match and current is not None:
            current["file_version"] = version_match.group("version")
            current["created_revision"] = version_match.group("created_revision")
            current["last_saved_revision"] = version_match.group("last_saved_revision")
            continue
        job_status_match = GUI_JOB_STATUS_RE.search(line)
        if job_status_match and current is not None:
            current["job_status_available"] = False
            current["job_status_path"] = job_status_match.group("path")
    return events
