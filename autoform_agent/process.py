"""这个文件处理 AutoForm 进程级动作，例如打开 Forming、打开 `.afd` 工程和运行求解器。它把命令、进程号和输出记录为后续证据。

This file handles AutoForm process-level actions such as opening Forming, opening `.afd` projects, and running the solver. It records commands, process IDs, and output as later evidence.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Sequence

from .paths import AutoFormInstallation, get_default_installation


# 小白读法：
# 这个文件负责“真正准备本机进程命令”。上层 MCP/CLI 只负责收参数；
# 到这里以后，代码会找到 AutoForm 安装目录，拼出 AFSplash.exe 或
# AFFormingUI.exe 的命令。dry_run=True 时只返回命令，不打开任何窗口。

def start_forming_ui(
    install: AutoFormInstallation | None = None,
    graphics: str = "directx11",
    dry_run: bool = False,
) -> list[str]:
    """Start the AutoForm GUI and return the exact command used."""

    install = install or get_default_installation()
    graphics_arg = _graphics_argument(graphics)
    # AFSplash.exe 是 AutoForm 的启动器；-afformingui 表示打开 Forming 主界面。
    # graphics_arg 只允许 directx11 或 opengl2，避免上层传入任意未知参数。
    command = [str(install.splash), "-afformingui", graphics_arg]
    if not dry_run:
        # Popen 会立即返回，不等待用户关闭 AutoForm。
        # 这样 CLI/MCP 调用不会卡死，AutoForm 窗口交给用户继续操作。
        subprocess.Popen(command, cwd=str(install.bin_dir))
    return command


def start_forming_ui_observer(
    install: AutoFormInstallation | None = None,
    graphics: str = "directx11",
    dry_run: bool = False,
) -> dict:
    """Start AutoForm Forming and return launch evidence including PID."""

    install = install or get_default_installation()
    graphics_arg = _graphics_argument(graphics)
    command = [str(install.splash), "-afformingui", graphics_arg]
    observation = {
        "mode": "gui_start_observer",
        "dry_run": dry_run,
        "command": command,
        "cwd": str(install.bin_dir),
        "launched": False,
        "pid": None,
        "evidence": "The command uses AFSplash.exe -afformingui to start AutoForm Forming.",
    }
    if dry_run:
        return observation

    process = subprocess.Popen(command, cwd=str(install.bin_dir))
    observation.update({"launched": True, "pid": process.pid})
    return observation


def open_afd(
    afd_path: Path,
    install: AutoFormInstallation | None = None,
    dry_run: bool = False,
) -> list[str]:
    """Open an .afd file in AutoForm Forming and return the launch command."""

    install = install or get_default_installation()
    # 先确认 .afd 文件真实存在。路径错了就直接报错，不去启动 AutoForm。
    afd_path = _existing_afd_path(afd_path)
    command = _open_afd_command(install, afd_path)
    if not dry_run:
        # 打开工程也是 GUI 动作，启动后由用户在 AutoForm 窗口里继续看。
        subprocess.Popen(command, cwd=str(install.bin_dir))
    return command


def open_afd_observer(
    afd_path: Path,
    install: AutoFormInstallation | None = None,
    dry_run: bool = True,
) -> dict:
    """Plan or launch an AutoForm GUI window for observing a project run.

    The direct solver remains the verified execution path.  This helper opens
    the copied `.afd` project in AutoForm Forming so a user can watch whatever
    the local AutoForm UI refreshes while the solver process writes results.
    The returned dictionary records the exact command, process id when known,
    and the evidence boundary for later debugging.
    """

    install = install or get_default_installation()
    afd_path = _existing_afd_path(afd_path)
    command = _open_afd_command(install, afd_path)
    observation = {
        "mode": "gui_project_observer",
        "dry_run": dry_run,
        "command": command,
        "cwd": str(install.bin_dir),
        "project_path": str(afd_path),
        "launched": False,
        "pid": None,
        "progress_visibility": "best_effort",
        "evidence": "The command uses AFFormingUI.exe -file with the same copied .afd project that the direct solver run uses.",
        "limitations": [
            "AutoForm controls whether an already opened project view refreshes live solver output.",
            "Solver success and failure are still determined from AFFormingSolver return code and stdout summary.",
        ],
    }
    if dry_run:
        return observation

    # `Popen` returns immediately so the MCP or CLI caller can continue to the
    # solver step while the GUI stays available as an interactive user window.
    process = subprocess.Popen(command, cwd=str(install.bin_dir))
    observation.update({"launched": True, "pid": process.pid})
    return observation


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


def _existing_afd_path(afd_path: Path) -> Path:
    """Resolve an `.afd` path and fail early before starting AutoForm."""
    resolved = afd_path.resolve()
    if not resolved.exists():
        raise FileNotFoundError(resolved)
    return resolved


def _open_afd_command(install: AutoFormInstallation, afd_path: Path) -> list[str]:
    """Build the stable AutoForm UI command used by dry runs and launches."""
    # AutoForm 打开工程的核心命令就是 AFFormingUI.exe -file <工程路径>。
    # start-ui 不带工程路径，open-afd 会带 -file。
    return [str(install.forming_ui), "-file", str(afd_path)]
