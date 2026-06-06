"""Create a new AutoForm project from a CAD geometry file with evidence."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
from typing import Any

from .gui_automation import (
    autoform_window_snapshot,
    autoform_window_tree_snapshot,
    capture_desktop_screenshot,
    click_autoform_window,
    paste_text_to_autoform,
    restore_autoform_window,
    send_autoform_keystroke,
)
from .process import start_forming_ui_observer


SCHEMA_VERSION = "autoform.geometry_import_to_new_project.v1"
SUPPORTED_GEOMETRY_SUFFIXES = {".step", ".stp", ".igs", ".iges", ".stl"}
DEFAULT_OUTPUT_ROOT = Path("output") / "geometry_import_projects"
DEFAULT_LENGTH_UNIT = "mm"
DEFAULT_GEOMETRY_TYPE = "part"
NEW_PROJECT_TITLE_CANDIDATES = ("Untitled", "无当前设计")


def import_geometry_to_new_project(
    source_geometry_path: str,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    output_afd_path: str | Path | None = None,
    length_unit: str = DEFAULT_LENGTH_UNIT,
    geometry_type: str = DEFAULT_GEOMETRY_TYPE,
    graphics: str = "directx11",
    gui_wait_seconds: float = 10,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Import one CAD geometry into a new AutoForm project and save an `.afd`."""

    started_at = _utc_now()
    steps: list[dict[str, Any]] = []
    screenshots: list[str] = []
    logs: list[str] = []
    run_dir = _run_dir(output_dir, source_geometry_path)
    evidence_dir = run_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    log_path = evidence_dir / "workflow_log.jsonl"
    logs.append(str(log_path.resolve()))

    def log_event(name: str, status: str, **payload: Any) -> None:
        record = {"time": _utc_now(), "name": name, "status": status, **payload}
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    try:
        source_path = resolve_geometry_source_path(source_geometry_path)
        _validate_geometry_source_path(source_path)
        afd_path = _safe_output_afd_path(source_path, run_dir, output_afd_path)
        context = _base_result(
            status="running",
            source_geometry_path=source_path,
            output_afd_path=afd_path,
            run_dir=run_dir,
            evidence_dir=evidence_dir,
            started_at=started_at,
            steps=steps,
            screenshots=screenshots,
            logs=logs,
        )
        dimension_candidate = _geometry_dimension_candidate_from_path(source_path, length_unit=length_unit)
        if dimension_candidate:
            context["geometry_dimension_candidate"] = dimension_candidate
        steps.append({"name": "validate_inputs", "status": "completed", "source": str(source_path), "output": str(afd_path)})
        log_event("validate_inputs", "completed", source=str(source_path), output=str(afd_path))
    except Exception as exc:
        log_event("validate_inputs", "failed", error_type=type(exc).__name__, error=str(exc))
        return _base_result(
            status="failed",
            source_geometry_path=str(source_geometry_path),
            output_afd_path="",
            run_dir=run_dir,
            evidence_dir=evidence_dir,
            started_at=started_at,
            steps=[{"name": "validate_inputs", "status": "failed", "error": str(exc)}],
            screenshots=screenshots,
            logs=logs,
            failure_reason=str(exc),
            finished_at=_utc_now(),
        )

    if dry_run:
        steps.extend(
            [
                {"name": "launch_or_attach", "status": "planned"},
                {"name": "new_project", "status": "planned"},
                {"name": "import_part_geometry", "status": "planned"},
                {"name": "save_afd", "status": "planned"},
            ]
        )
        log_event("dry_run", "planned")
        return {
            **context,
            "status": "planned",
            "length_unit": length_unit,
            "geometry_type": geometry_type,
            "graphics": graphics,
            "dry_run": True,
            "finished_at": _utc_now(),
        }

    try:
        result = _run_gui_import_sequence(
            source_path=source_path,
            output_afd_path=afd_path,
            evidence_dir=evidence_dir,
            screenshots=screenshots,
            steps=steps,
            log_event=log_event,
            length_unit=length_unit,
            geometry_type=geometry_type,
            graphics=graphics,
            gui_wait_seconds=gui_wait_seconds,
        )
    except Exception as exc:
        log_event("workflow", "failed", error_type=type(exc).__name__, error=str(exc))
        _capture_evidence(
            evidence_dir=evidence_dir,
            screenshots=screenshots,
            name="99_failed",
            steps=steps,
            log_event=log_event,
            wait_seconds=0.2,
        )
        return {
            **context,
            "status": "failed",
            "length_unit": length_unit,
            "geometry_type": geometry_type,
            "graphics": graphics,
            "failure_reason": str(exc),
            "finished_at": _utc_now(),
        }

    status = "completed" if afd_path.exists() and afd_path.stat().st_size > 0 else "blocked"
    if status == "blocked":
        if not result.get("blocked_reason"):
            result["blocked_reason"] = "AutoForm did not create the requested .afd output file."
        log_event("verify_output_afd", "blocked", output=str(afd_path))
    else:
        steps.append(
            {
                "name": "verify_output_afd",
                "status": "completed",
                "output": str(afd_path),
                "size_bytes": afd_path.stat().st_size,
            }
        )
        log_event("verify_output_afd", "completed", output=str(afd_path), size_bytes=afd_path.stat().st_size)

    finished = {
        **context,
        **result,
        "status": status,
        "length_unit": length_unit,
        "geometry_type": geometry_type,
        "graphics": graphics,
        "dry_run": False,
        "finished_at": _utc_now(),
    }
    manifest_path = evidence_dir / "manifest.json"
    manifest_path.write_text(json.dumps(finished, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    logs.append(str(manifest_path.resolve()))
    finished["logs"] = logs
    return finished


def resolve_geometry_source_path(source_geometry_path: str | Path, *, base_dir: str | Path | None = None) -> Path:
    """Resolve absolute paths, workspace-relative paths, desktop file names, and desktop phrases."""

    raw = _geometry_filename_fragment(source_geometry_path)
    if not raw:
        raise ValueError("source_geometry_path is required")
    path = Path(raw)
    candidates = []
    if path.is_absolute():
        candidates.append(path)
    else:
        root = Path(base_dir or Path.cwd())
        candidates.append((root / path).resolve())
        desktop = Path.home() / "Desktop"
        candidates.append((desktop / path.name).resolve())
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    if path.is_absolute():
        return path.resolve()
    return candidates[0]


def extract_geometry_path_from_text(text: str, *, base_dir: str | Path | None = None) -> str:
    """Extract a supported CAD path or desktop file name from prompt text."""

    prompt = str(text or "")
    if not prompt.strip():
        return ""
    suffix_pattern = r"(?:step|stp|igs|iges|stl)"
    patterns = (
        rf'"([^"\r\n]+?\.{suffix_pattern})"',
        rf"'([^'\r\n]+?\.{suffix_pattern})'",
        rf"`([^`\r\n]+?\.{suffix_pattern})`",
        rf"“([^”\r\n]+?\.{suffix_pattern})”",
        rf"‘([^’\r\n]+?\.{suffix_pattern})’",
        rf"「([^」\r\n]+?\.{suffix_pattern})」",
        rf"『([^』\r\n]+?\.{suffix_pattern})』",
        rf"《([^》\r\n]+?\.{suffix_pattern})》",
        rf"([A-Za-z]:[^\r\n\"'`]+?\.{suffix_pattern})",
        rf"(\\\\[^\r\n\"'`]+?\.{suffix_pattern})",
        rf"([\w\u4e00-\u9fff][^\\/:*?\"<>|“”‘’「」『』《》\r\n]*?\.{suffix_pattern})",
    )
    for pattern in patterns:
        match = re.search(pattern, prompt, flags=re.IGNORECASE)
        if not match:
            continue
        candidate = next((group for group in match.groups() if group), "")
        candidate = _geometry_filename_fragment(candidate)
        if not candidate:
            continue
        resolved = resolve_geometry_source_path(candidate, base_dir=base_dir)
        if resolved.exists() or Path(candidate).suffix.casefold() in SUPPORTED_GEOMETRY_SUFFIXES:
            return str(resolved if resolved.exists() else candidate)
    return ""


def _run_gui_import_sequence(
    *,
    source_path: Path,
    output_afd_path: Path,
    evidence_dir: Path,
    screenshots: list[str],
    steps: list[dict[str, Any]],
    log_event,
    length_unit: str,
    geometry_type: str,
    graphics: str,
    gui_wait_seconds: float,
) -> dict[str, Any]:
    gui_pid = None
    launch = start_forming_ui_observer(graphics=graphics, dry_run=False)
    gui_pid = launch.get("pid")
    steps.append({"name": "launch_or_attach", "status": "completed", "pid": gui_pid, "command": launch.get("command")})
    log_event("launch_or_attach", "completed", pid=gui_pid, command=launch.get("command"))
    time.sleep(max(float(gui_wait_seconds), 0))
    readiness = _ensure_autoform_window_ready(wait_seconds=0.5)
    steps.append({"name": "ensure_gui_ready_after_launch", "status": readiness.get("status"), "evidence": readiness})
    log_event("ensure_gui_ready_after_launch", readiness.get("status"), evidence=readiness)
    _capture_evidence(
        evidence_dir=evidence_dir,
        screenshots=screenshots,
        name="01_after_launch",
        steps=steps,
        log_event=log_event,
        wait_seconds=0.2,
        title_contains="Untitled",
    )

    new_shortcut = send_autoform_keystroke("control+n", focus_first=True, restore_window=True, wait_seconds=0.2)
    click = click_autoform_window(0.89, 0.45, relative=True, restore_window=True, wait_seconds=0.2)
    steps.append(
        {
            "name": "new_project",
            "status": "completed" if new_shortcut.get("sent") or click.get("clicked") else "attempted",
            "shortcut": new_shortcut,
            "fallback_click": click,
        }
    )
    log_event("new_project", "completed" if new_shortcut.get("sent") or click.get("clicked") else "attempted", shortcut=new_shortcut, fallback_click=click)
    time.sleep(1.0)
    readiness = _ensure_autoform_window_ready(wait_seconds=0.2)
    steps.append({"name": "ensure_gui_ready_after_new_project", "status": readiness.get("status"), "evidence": readiness})
    log_event("ensure_gui_ready_after_new_project", readiness.get("status"), evidence=readiness)
    _capture_evidence(
        evidence_dir=evidence_dir,
        screenshots=screenshots,
        name="02_after_new_project",
        steps=steps,
        log_event=log_event,
        wait_seconds=0.2,
        title_contains="Untitled",
    )

    if geometry_type.casefold() not in {"part", "零件", "part_geometry"}:
        steps.append({"name": "geometry_type", "status": "blocked", "requested": geometry_type})
        return {"gui_pid": gui_pid, "blocked_reason": f"Unsupported geometry_type for current GUI automation: {geometry_type}"}

    click = _click_new_project_window(0.26, 0.415, wait_seconds=0.2)
    steps.append({"name": "open_import_dialog", "status": "completed" if click.get("clicked") else "attempted", "evidence": click})
    log_event("open_import_dialog", "completed" if click.get("clicked") else "attempted", evidence=click)
    time.sleep(0.8)
    _capture_evidence(
        evidence_dir=evidence_dir,
        screenshots=screenshots,
        name="03_import_dialog",
        steps=steps,
        log_event=log_event,
        wait_seconds=0.2,
        focus_autoform=False,
    )

    pasted = paste_text_to_autoform(str(source_path), focus_first=False, restore_window=False, wait_seconds=0.1)
    entered = send_autoform_keystroke("enter", focus_first=False, wait_seconds=0.1)
    steps.append({"name": "select_geometry_path", "status": "completed" if pasted.get("pasted") else "failed", "paste": pasted, "enter": entered})
    log_event("select_geometry_path", "completed" if pasted.get("pasted") else "failed", paste=pasted, enter=entered)
    time.sleep(3.0)
    _capture_evidence(
        evidence_dir=evidence_dir,
        screenshots=screenshots,
        name="04_after_import",
        steps=steps,
        log_event=log_event,
        wait_seconds=0.2,
        title_contains="Untitled",
    )

    save = _send_new_project_keystroke("control+s", wait_seconds=0.2)
    steps.append({"name": "open_save_dialog", "status": "completed" if save.get("sent") else "failed", "evidence": save})
    log_event("open_save_dialog", "completed" if save.get("sent") else "failed", evidence=save)
    time.sleep(0.8)
    pasted = paste_text_to_autoform(str(output_afd_path), focus_first=False, restore_window=False, wait_seconds=0.1)
    entered = send_autoform_keystroke("enter", focus_first=False, wait_seconds=0.1)
    steps.append({"name": "save_afd", "status": "completed" if pasted.get("pasted") else "failed", "output": str(output_afd_path), "paste": pasted, "enter": entered})
    log_event("save_afd", "completed" if pasted.get("pasted") else "failed", output=str(output_afd_path), paste=pasted, enter=entered)
    time.sleep(3.0)
    _capture_evidence(
        evidence_dir=evidence_dir,
        screenshots=screenshots,
        name="05_after_save",
        steps=steps,
        log_event=log_event,
        wait_seconds=0.2,
    )

    return {"gui_pid": gui_pid, "blocked_reason": ""}


def _ensure_autoform_window_ready(*, wait_seconds: float) -> dict[str, Any]:
    """Restore a visible AutoForm window when a GUI workflow is about to interact."""

    snapshot = autoform_window_snapshot()
    if snapshot.get("interaction_ready_window_count", 0) > 0:
        return {"status": "already_ready", "snapshot": snapshot}
    restore = restore_autoform_window(wait_seconds=wait_seconds)
    after = autoform_window_snapshot()
    return {
        "status": "ready" if after.get("interaction_ready_window_count", 0) > 0 else "not_ready",
        "restore": restore,
        "snapshot": after,
    }


def _new_project_title_candidates() -> list[str | None]:
    snapshot = autoform_window_snapshot()
    candidates: list[str | None] = list(NEW_PROJECT_TITLE_CANDIDATES)
    if snapshot.get("window_count", 0) == 1:
        candidates.append(None)
    return candidates


def _click_new_project_window(x: float, y: float, *, wait_seconds: float) -> dict[str, Any]:
    attempts = []
    for title in _new_project_title_candidates():
        result = click_autoform_window(
            x,
            y,
            relative=True,
            restore_window=True,
            title_contains=title,
            wait_seconds=wait_seconds,
        )
        attempts.append(result)
        if result.get("clicked"):
            return {**result, "attempts": attempts}
    return {"clicked": False, "reason": "new_project_window_not_ready", "attempts": attempts}


def _send_new_project_keystroke(keys: str, *, wait_seconds: float) -> dict[str, Any]:
    attempts = []
    for title in _new_project_title_candidates():
        result = send_autoform_keystroke(
            keys,
            focus_first=True,
            restore_window=True,
            title_contains=title,
            wait_seconds=wait_seconds,
        )
        attempts.append(result)
        if result.get("sent"):
            return {**result, "attempts": attempts}
    return {"sent": False, "reason": "new_project_window_not_ready", "attempts": attempts}


def _capture_evidence(
    *,
    evidence_dir: Path,
    screenshots: list[str],
    name: str,
    steps: list[dict[str, Any]],
    log_event,
    wait_seconds: float,
    focus_autoform: bool = True,
    title_contains: str | None = None,
) -> None:
    screenshot_path = evidence_dir / f"{name}.png"
    tree_path = evidence_dir / f"{name}_window_tree.json"
    snapshot_path = evidence_dir / f"{name}_window_snapshot.json"
    try:
        screenshot = capture_desktop_screenshot(
            screenshot_path,
            focus_autoform=focus_autoform,
            title_contains=title_contains,
            wait_seconds=wait_seconds,
        )
        screenshots.append(str(screenshot_path.resolve()))
        steps.append({"name": f"capture_{name}", "status": "completed", "screenshot": screenshot})
        log_event(f"capture_{name}", "completed", screenshot=screenshot)
    except Exception as exc:
        steps.append({"name": f"capture_{name}", "status": "failed", "error": str(exc)})
        log_event(f"capture_{name}", "failed", error_type=type(exc).__name__, error=str(exc))
    for path, factory, event_name in (
        (snapshot_path, autoform_window_snapshot, "window_snapshot"),
        (tree_path, autoform_window_tree_snapshot, "window_tree"),
    ):
        try:
            data = factory()
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            log_event(f"{event_name}_{name}", "completed", path=str(path.resolve()))
        except Exception as exc:
            log_event(f"{event_name}_{name}", "failed", error_type=type(exc).__name__, error=str(exc))


def _safe_output_afd_path(source_path: Path, run_dir: Path, output_afd_path: str | Path | None) -> Path:
    if output_afd_path:
        requested = Path(output_afd_path)
        requested = requested if requested.is_absolute() else run_dir / requested.name
        if requested.exists():
            path = run_dir / _safe_afd_name(requested.stem)
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                raise FileExistsError(f"Refusing to overwrite existing output file: {path}")
            return path.resolve()
        path = requested
    else:
        path = run_dir / _safe_afd_name(source_path.stem)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing output file: {path}")
    return path.resolve()


def _validate_geometry_source_path(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"source_geometry_path does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"source_geometry_path must be a file: {path}")
    if path.suffix.casefold() not in SUPPORTED_GEOMETRY_SUFFIXES:
        raise ValueError(f"Unsupported geometry file extension: {path.suffix}")


def _run_dir(output_dir: str | Path, source_geometry_path: str | Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = _safe_stem(Path(_geometry_filename_fragment(source_geometry_path)).stem or "geometry")
    root = Path(output_dir or DEFAULT_OUTPUT_ROOT)
    candidate = (root / f"{timestamp}_{stem}").resolve()
    if not candidate.exists():
        return candidate
    for index in range(2, 1000):
        alternate = (root / f"{timestamp}_{stem}_{index}").resolve()
        if not alternate.exists():
            return alternate
    raise FileExistsError(f"Could not allocate a unique geometry import run directory under {root}")


def _safe_stem(value: str) -> str:
    stem = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_.-]+", "_", str(value or "geometry")).strip("._ ")
    return stem[:80] or "geometry"


def _safe_afd_name(stem: str) -> str:
    return f"{_safe_stem(stem)}.afd"


def _strip_path_text(value: str | Path) -> str:
    text = str(value or "").strip()
    for marker in ("桌面上的", "桌面上", "桌面里的", "桌面里"):
        index = text.rfind(marker)
        if index >= 0:
            text = text[index + len(marker):].strip()
    for prefix in ("desktop:", "Desktop:"):
        if text.casefold().startswith(prefix.casefold()):
            text = text[len(prefix):].strip()
    return text.strip(" \t\r\n\"'`“”‘’。，；;、（）()[]{}<>")


def _geometry_filename_fragment(value: str | Path) -> str:
    """Extract the actual geometry filename/path from descriptive prompt text."""

    text = _strip_path_text(value)
    if not text:
        return ""
    suffix_pattern = r"(?:step|stp|igs|iges|stl)"
    quoted_parts = re.split(r"[\"'`“”‘’「」『』《》]", text)
    for part in reversed(quoted_parts):
        candidate = _strip_path_text(part)
        if re.search(rf"\.{suffix_pattern}$", candidate, flags=re.IGNORECASE):
            return candidate
    if re.match(r"^[A-Za-z]:", text) or text.startswith("\\\\") or "\\" in text or "/" in text:
        return text
    matches = re.findall(
        rf"([^\s\\/:*?\"<>|“”‘’「」『』《》，,。；;、（）()\[\]{{}}]+?\.{suffix_pattern})",
        text,
        flags=re.IGNORECASE,
    )
    if matches:
        return _strip_path_text(matches[-1])
    return text


def _geometry_dimension_candidate_from_path(path: Path, *, length_unit: str) -> dict[str, Any] | None:
    """Infer a length-width-thickness candidate from common filename patterns."""

    stem = path.stem
    match = re.search(r"(\d+(?:\.\d+)?)\s*[-xX×*]\s*(\d+(?:\.\d+)?)\s*[-xX×*]\s*(\d+(?:\.\d+)?)", stem)
    if not match:
        return None
    length, width, thickness = (float(value) for value in match.groups())
    return {
        "status": "candidate_from_filename",
        "length": int(length) if length.is_integer() else length,
        "width": int(width) if width.is_integer() else width,
        "thickness": int(thickness) if thickness.is_integer() else thickness,
        "unit": length_unit,
        "evidence": path.name,
        "confidence": "medium",
        "note": "Parsed from filename pattern; not measured from CAD geometry.",
    }


def _base_result(
    *,
    status: str,
    source_geometry_path: str | Path,
    output_afd_path: str | Path,
    run_dir: Path,
    evidence_dir: Path,
    started_at: str,
    steps: list[dict[str, Any]],
    screenshots: list[str],
    logs: list[str],
    failure_reason: str = "",
    blocked_reason: str = "",
    finished_at: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "source_geometry_path": str(source_geometry_path),
        "output_afd_path": str(output_afd_path),
        "gui_pid": None,
        "screenshots": screenshots,
        "logs": logs,
        "evidence_dir": str(evidence_dir.resolve()),
        "run_dir": str(run_dir.resolve()),
        "failure_reason": failure_reason,
        "blocked_reason": blocked_reason,
        "steps": steps,
        "started_at": started_at,
        "finished_at": finished_at,
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "DEFAULT_OUTPUT_ROOT",
    "SUPPORTED_GEOMETRY_SUFFIXES",
    "extract_geometry_path_from_text",
    "import_geometry_to_new_project",
    "resolve_geometry_source_path",
]
