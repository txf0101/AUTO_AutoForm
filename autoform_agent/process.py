"""Process-level entry points for AutoForm GUI and batch commands.

This module owns the boundary where Python starts AutoForm processes.  Callers
should prefer the planning or dry-run modes first, because launching GUI or job
processes may consume licenses, create logs, or modify project state.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Sequence

from .paths import AutoFormInstallation, get_default_installation


def start_forming_ui(
    install: AutoFormInstallation | None = None,
    graphics: str = "directx11",
    dry_run: bool = False,
) -> list[str]:
    """Start the AutoForm GUI and return the exact command used."""

    install = install or get_default_installation()
    graphics_arg = _graphics_argument(graphics)
    command = [str(install.splash), "-afformingui", graphics_arg]
    if not dry_run:
        # Popen intentionally returns immediately; the GUI becomes the user's
        # interactive process after launch.
        subprocess.Popen(command, cwd=str(install.bin_dir))
    return command


def open_afd(
    afd_path: Path,
    install: AutoFormInstallation | None = None,
    dry_run: bool = False,
) -> list[str]:
    """Open an .afd file in AutoForm Forming and return the launch command."""

    install = install or get_default_installation()
    afd_path = afd_path.resolve()
    if not afd_path.exists():
        raise FileNotFoundError(afd_path)
    command = [str(install.forming_ui), "-file", str(afd_path)]
    if not dry_run:
        # Opening a project is a GUI action, so the caller should not block on
        # process exit.
        subprocess.Popen(command, cwd=str(install.bin_dir))
    return command


def run_forming_job(
    args: Sequence[str],
    install: AutoFormInstallation | None = None,
    dry_run: bool = False,
    timeout: int | None = None,
    working_dir: Path | None = None,
) -> subprocess.CompletedProcess[str] | list[str]:
    """Run AFFormingJob for batch-style operations once arguments are known."""

    install = install or get_default_installation()
    command = [str(install.forming_job), *args]
    if dry_run:
        return command
    return subprocess.run(
        command,
        cwd=str((working_dir or Path.cwd()).resolve()),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def forming_job_plan(
    args: Sequence[str],
    install: AutoFormInstallation | None = None,
    working_dir: Path | None = None,
) -> dict:
    """Return a structured AFFormingJob command preview."""

    install = install or get_default_installation()
    cwd = (working_dir or Path.cwd()).resolve()
    return {
        "command": [str(install.forming_job), *args],
        "working_dir": str(cwd),
        "executable_exists": install.forming_job.exists(),
        "arg_count": len(args),
        "has_args": bool(args),
    }


def collect_forming_job_logs(search_dir: Path, limit: int = 20) -> list[dict]:
    """Return local AFFormingJob log file metadata and short previews."""

    root = search_dir.resolve()
    if not root.exists():
        return []
    logs = sorted(root.glob("log_AFFormingJob_*.txt"), key=lambda path: path.stat().st_mtime, reverse=True)
    results: list[dict] = []
    for path in logs[:limit]:
        stat = path.stat()
        preview = path.read_text(encoding="utf-8", errors="replace")[:500] if stat.st_size else ""
        results.append(
            {
                "name": path.name,
                "path": str(path),
                "size_bytes": stat.st_size,
                "last_modified": stat.st_mtime,
                "preview": preview,
            }
        )
    return results


def _graphics_argument(graphics: str) -> str:
    """Map friendly graphics names to AutoForm launcher flags."""
    normalized = graphics.lower().strip()
    if normalized in {"directx", "directx11", "dx11"}:
        return "-directx11"
    if normalized in {"opengl", "opengl2", "gl2"}:
        return "-opengl2"
    raise ValueError("graphics must be directx11 or opengl2")
