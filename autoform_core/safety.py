"""这个文件处理安全扫描、脱敏和公开发布边界。它的重点是发现明文密钥、敏感路径或不该公开的内容。

This file handles safety scanning, redaction, and public-release boundaries. Its main job is to find raw secrets, sensitive paths, or content that should not be published.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import re


SECRET_PATTERNS = {
    "provider_api_key": re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    "generic_assignment": re.compile(r"(?i)(api[_-]?key|token|secret)\s*=\s*['\"]?([A-Za-z0-9_./:+-]{16,})"),
}
SKIP_DIRS = {".git", ".pytest_cache", "__pycache__", "tmp", "output"}
SKIP_PATH_PREFIXES = {("data", "runtime", "agent")}
TEXT_EXTENSIONS = {".py", ".md", ".toml", ".yml", ".yaml", ".json", ".js", ".css", ".html", ".ps1", ".cmd", ".txt", ".example"}


def public_release_scan(project_root: str | Path | None = None) -> dict:
    """Scan tracked-style source files for common secret patterns before publication."""

    root = Path(project_root or Path.cwd()).resolve()
    findings = []
    seen_locations = set()
    for path in _iter_text_files(root):
        text = path.read_text(encoding="utf-8", errors="replace")
        for name, pattern in SECRET_PATTERNS.items():
            for match in pattern.finditer(text):
                # Generic assignment matches contain both the variable name and
                # the assigned value.  Secret-specific patterns only contain
                # the candidate token itself.  Keeping the value separate makes
                # placeholder and code-reference filtering predictable.
                value = match.group(match.lastindex or 0)
                if _is_code_reference(value):
                    continue
                if _is_placeholder(value):
                    continue
                line = text.count("\n", 0, match.start()) + 1
                location = (path, line)
                if location in seen_locations:
                    continue
                seen_locations.add(location)
                findings.append(
                    {
                        "kind": name,
                        "path": str(path),
                        "relative_path": str(path.relative_to(root)),
                        "line": line,
                        "preview": _redact(value),
                    }
                )
    env_file = root / ".env"
    return {
        "schema_version": "1.0",
        "checked_at": _utc_now(),
        "project_root": str(root),
        "safe_to_publish": not findings and not env_file.exists(),
        "finding_count": len(findings),
        "findings": findings,
        "env_file_present": env_file.exists(),
        "skipped_dirs": sorted(SKIP_DIRS) + ["/".join(prefix) for prefix in sorted(SKIP_PATH_PREFIXES)],
    }


def write_safety_plan(
    targets: list[str | Path],
    *,
    backup_root: str | Path = "output/rollback",
    dry_run: bool = True,
) -> dict:
    """Return backup and rollback facts for planned write targets."""

    root = Path(backup_root).resolve()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    entries = []
    for target in targets:
        path = Path(target).resolve()
        backup_path = root / timestamp / path.drive.replace(":", "") / Path(*path.parts[1:])
        entries.append(
            {
                "target": str(path),
                "exists": path.exists(),
                "parent_exists": path.parent.exists(),
                "parent_writable": os.access(path.parent, os.W_OK) if path.parent.exists() else False,
                "backup_path": str(backup_path),
                "rollback_action": "copy_backup_over_target" if path.exists() else "delete_created_target",
            }
        )
    return {
        "schema_version": "1.0",
        "created_at": _utc_now(),
        "dry_run": dry_run,
        "backup_root": str(root),
        "targets": entries,
    }


def _iter_text_files(root: Path):
    """Yield source-like text files while avoiding generated artifacts."""

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative_parts = path.relative_to(root).parts
        if any(part in SKIP_DIRS for part in relative_parts):
            continue
        if any(relative_parts[: len(prefix)] == prefix for prefix in SKIP_PATH_PREFIXES):
            continue
        if path.name == ".env":
            continue
        if path.suffix.lower() in TEXT_EXTENSIONS or path.name.endswith(".example"):
            yield path


def _is_placeholder(value: str) -> bool:
    """Ignore documented placeholder values that are safe to publish."""

    lowered = value.casefold()
    return "your_" in lowered or "placeholder" in lowered or "example" in lowered


def _is_code_reference(value: str) -> bool:
    """Ignore member-access expressions such as `appState.apiConfig.apiKey`."""

    return bool(re.fullmatch(r"[A-Za-z_$][\w$]*(\.[A-Za-z_$][\w$]*)+", value))


def _redact(value: str) -> str:
    """Return a short redacted preview for a possible secret."""

    if len(value) <= 10:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def _utc_now() -> str:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()
