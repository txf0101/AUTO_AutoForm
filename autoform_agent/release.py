"""这个文件检查交付资料是否齐全。它读取 README、安装说明、环境文件、发布清单和新手文档等证据，给出发布就绪判断。

This file checks whether delivery materials are complete. It reads evidence such as README, installation notes, environment files, release checklists, and beginner documentation to judge release readiness.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import re

from .safety import public_release_scan


PROJECT_RELEASE_VERSION = "1.4.0"
PROJECT_RELEASE_DIR_NAME = "autoform-agent-1.4"

REQUIRED_RELEASE_FILES = [
    "README.md",
    "DEVELOPERS.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "INSTALL.md",
    "UNINSTALL.md",
    "LICENSE",
    "RELEASE_CHECKLIST.md",
    "environment.yml",
    "pyproject.toml",
    "codex_mcp_config.autoform-agent.toml",
    "docs/beginner_onboarding_zh.md",
    "docs/api_runtime_call_chain.md",
    "docs/multi_agent_architecture.md",
    "docs/v1_4_release_notes.md",
]

PACKAGE_INCLUDE_DIRS = ["autoform_agent", "docs", "frontend", "tests", "tools"]
PACKAGE_INCLUDE_FILES = [
    ".env.example",
    "AGENTS.md",
    "CHANGELOG.md",
    "CODEX_TASK_PROMPT.md",
    "CONTRIBUTING.md",
    "DEVELOPERS.md",
    "INSTALL.md",
    "LICENSE",
    "README.md",
    "RELEASE_CHECKLIST.md",
    "UNINSTALL.md",
    "codex_mcp_config.autoform-agent.toml",
    "environment.yml",
    "pyproject.toml",
    "start_autoform_agent.cmd",
    "start_autoform_agent.ps1",
]


def release_readiness_check(project_root: str | Path | None = None) -> dict:
    """Return release-readiness facts for the current workspace."""

    root = Path(project_root or Path.cwd()).resolve()
    files = [_file_check(root, relative) for relative in REQUIRED_RELEASE_FILES]
    missing = [item["relative_path"] for item in files if not item["exists"]]
    version = _pyproject_version(root / "pyproject.toml")
    license_check = _license_check(root / "LICENSE")
    public_scan = public_release_scan(root)
    ready = not missing and version == PROJECT_RELEASE_VERSION and license_check["is_mit"] and public_scan["safe_to_publish"]
    return {
        "schema_version": "1.0",
        "checked_at": _utc_now(),
        "project_root": str(root),
        "ready": ready,
        "missing_files": missing,
        "version": version,
        "version_ready": version == PROJECT_RELEASE_VERSION,
        "expected_version": PROJECT_RELEASE_VERSION,
        "license": license_check,
        "public_release_scan": public_scan,
        "required_files": files,
        "package_plan": release_package_plan(root / "output" / "release" / PROJECT_RELEASE_DIR_NAME, project_root=root, dry_run=True),
    }


def release_package_plan(
    output_dir: str | Path,
    *,
    project_root: str | Path | None = None,
    dry_run: bool = True,
) -> dict:
    """Plan or create a source release directory with explicit included files."""

    root = Path(project_root or Path.cwd()).resolve()
    destination = Path(output_dir).resolve()
    planned_files = []
    for relative in PACKAGE_INCLUDE_FILES:
        source = root / relative
        planned_files.append(_copy_plan(source, destination / relative, root))
    for relative_dir in PACKAGE_INCLUDE_DIRS:
        source_dir = root / relative_dir
        if not source_dir.exists():
            planned_files.append(_copy_plan(source_dir, destination / relative_dir, root))
            continue
        for source in source_dir.rglob("*"):
            if source.is_file() and "__pycache__" not in source.parts:
                planned_files.append(_copy_plan(source, destination / source.relative_to(root), root))

    plan = {
        "schema_version": "1.0",
        "created_at": _utc_now(),
        "project_root": str(root),
        "destination": str(destination),
        "dry_run": dry_run,
        "file_count": len(planned_files),
        "planned_files": planned_files,
        "exclusions": ["output", "tmp", ".pytest_cache", "autoform_agent_data", ".env", "__pycache__"],
    }
    if dry_run:
        return plan

    destination.mkdir(parents=True, exist_ok=True)
    for item in planned_files:
        source = Path(item["source"])
        if not source.exists() or not source.is_file():
            continue
        target = Path(item["destination"])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    (destination / "release_manifest.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return plan


def install_check_plan(project_root: str | Path | None = None) -> dict:
    """Return manual install checks and commands grounded in project files."""

    root = Path(project_root or Path.cwd()).resolve()
    return {
        "project_root": str(root),
        "steps": [
            {
                "name": "create_environment",
                "command": "conda env create -f environment.yml",
                "evidence": "environment.yml",
                "required": True,
            },
            {
                "name": "activate_environment",
                "command": "conda activate afagent",
                "evidence": "environment.yml name field",
                "required": True,
            },
            {
                "name": "copy_env_template",
                "command": "Copy-Item .env.example .env",
                "evidence": ".env.example",
                "required": False,
            },
            {
                "name": "check_status",
                "command": "python -m autoform_agent.cli status",
                "evidence": "autoform_agent.diagnostics.autoform_status_snapshot",
                "required": True,
            },
            {
                "name": "run_tests",
                "command": "python -m pytest -q",
                "evidence": "pyproject.toml testpaths",
                "required": True,
            },
        ],
    }


def _file_check(root: Path, relative: str) -> dict:
    """Return existence and size for one release file."""
    path = root / relative
    return {
        "relative_path": relative,
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() and path.is_file() else None,
    }


def _copy_plan(source: Path, destination: Path, root: Path) -> dict:
    """Return one source-to-release copy record."""
    return {
        "relative_path": str(source.relative_to(root)) if source.exists() else str(source),
        "source": str(source),
        "destination": str(destination),
        "exists": source.exists(),
        "size_bytes": source.stat().st_size if source.exists() and source.is_file() else None,
    }


def _pyproject_version(path: Path) -> str | None:
    """Read the project version from pyproject.toml without adding dependencies."""

    if not path.exists():
        return None
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', path.read_text(encoding="utf-8", errors="replace"))
    return match.group(1) if match else None


def _license_check(path: Path) -> dict:
    """Return whether the license file contains the MIT license heading."""

    text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    return {
        "path": str(path),
        "exists": path.exists(),
        "is_mit": "MIT License" in text and "Permission is hereby granted" in text,
    }


def _utc_now() -> str:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()
