"""Assign an AutoForm material file to an existing project with GUI evidence."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import time
from typing import Any

from .gui_automation import (
    autoform_window_snapshot,
    autoform_window_tree_snapshot,
    capture_desktop_screenshot,
    click_autoform_window,
    focus_autoform_window,
    paste_text_to_autoform,
    send_autoform_keystroke,
)
from .inventory import get_afd_project_summary, get_afd_readable_index
from .materials import inspect_material_file
from .paths import get_default_installation
from .process import open_afd_observer


SCHEMA_VERSION = "autoform.material_assignment.v1"
DEFAULT_OUTPUT_ROOT = Path("output") / "material_assignment"
DEFAULT_BACKUP_ROOT = Path("output") / "material_assignment_backups"
SUPPORTED_MATERIAL_SUFFIXES = {".mtb", ".mat"}
PROFILE_ID = "concept_geometry_material_add_v1"


def assign_material_to_project(
    afd_path: str | None = None,
    material_path: str | None = None,
    material_grade: str | None = None,
    material_temper: str | None = None,
    project_resolution: str = "current_or_prompt",
    graphics: str = "directx11",
    gui_wait_seconds: float = 10,
    save_project: bool = True,
    dry_run: bool = False,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    backup_root: str | Path = DEFAULT_BACKUP_ROOT,
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    """Assign a material file to one existing `.afd` project.

    Real execution uses the AutoForm GUI and writes the original project file.
    The source project is backed up before any GUI action is attempted.
    """

    started_at = _utc_now()
    steps: list[dict[str, Any]] = []
    screenshots: list[str] = []
    window_trees: list[str] = []
    logs: list[str] = []
    project_root_path = Path(project_root or Path.cwd()).resolve()
    output_root = Path(output_dir)
    run_dir = _run_dir(output_root, material_path or material_grade or afd_path or "material_assignment")
    evidence_dir = run_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    log_path = evidence_dir / "workflow_log.jsonl"
    logs.append(str(log_path.resolve()))

    def log_event(name: str, status: str, **payload: Any) -> None:
        record = {"time": _utc_now(), "name": name, "status": status, **payload}
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    try:
        resolved_afd = resolve_assignment_project_path(
            afd_path,
            project_resolution=project_resolution,
            project_root=project_root_path,
        )
        resolved_material = resolve_assignment_material_path(material_path, project_root=project_root_path)
        before_summary = _safe_afd_summary(resolved_afd)
        before_fragments = _safe_afd_material_fragments(resolved_afd)
        material_info = inspect_material_file(resolved_material, preview_lines=5, hash_contents=True)
        steps.append(
            {
                "name": "validate_inputs",
                "status": "completed",
                "afd_path": str(resolved_afd),
                "material_path": str(resolved_material),
            }
        )
        log_event("validate_inputs", "completed", afd_path=str(resolved_afd), material_path=str(resolved_material))
    except AmbiguousProjectError as exc:
        return _blocked_result(
            status="blocked_project_path_ambiguous",
            blocked_reason=str(exc),
            started_at=started_at,
            run_dir=run_dir,
            evidence_dir=evidence_dir,
            logs=logs,
            steps=[{"name": "validate_inputs", "status": "blocked", "candidates": exc.candidates}],
            extra={"project_candidates": exc.candidates},
        )
    except ProjectResolutionError as exc:
        return _blocked_result(
            status="blocked_project_path_required",
            blocked_reason=str(exc),
            started_at=started_at,
            run_dir=run_dir,
            evidence_dir=evidence_dir,
            logs=logs,
            steps=[{"name": "validate_inputs", "status": "blocked", "error": str(exc)}],
        )
    except AmbiguousMaterialError as exc:
        return _blocked_result(
            status="blocked_material_path_ambiguous",
            blocked_reason=str(exc),
            started_at=started_at,
            run_dir=run_dir,
            evidence_dir=evidence_dir,
            logs=logs,
            steps=[{"name": "validate_inputs", "status": "blocked", "candidates": exc.candidates}],
            extra={"material_candidates": exc.candidates},
        )
    except MaterialResolutionError as exc:
        return _blocked_result(
            status="blocked_material_path_required",
            blocked_reason=str(exc),
            started_at=started_at,
            run_dir=run_dir,
            evidence_dir=evidence_dir,
            logs=logs,
            steps=[{"name": "validate_inputs", "status": "blocked", "error": str(exc)}],
        )
    except Exception as exc:
        return _failed_result(
            failure_reason=str(exc),
            started_at=started_at,
            run_dir=run_dir,
            evidence_dir=evidence_dir,
            logs=logs,
            steps=[{"name": "validate_inputs", "status": "failed", "error": str(exc)}],
        )

    backup_dir = _backup_dir(Path(backup_root), resolved_afd)
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_project_path = backup_dir / resolved_afd.name
    shutil.copy2(resolved_afd, backup_project_path)
    before_summary_path = backup_dir / "before_project_summary.json"
    before_fragments_path = backup_dir / "before_material_fragments.json"
    inputs_path = backup_dir / "assignment_inputs.json"
    before_summary_path.write_text(json.dumps(before_summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    before_fragments_path.write_text(json.dumps(before_fragments, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    inputs_path.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "afd_path": str(resolved_afd),
                "material_path": str(resolved_material),
                "material_grade": material_grade,
                "material_temper": material_temper,
                "dry_run": dry_run,
                "save_project": save_project,
                "created_at": _utc_now(),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    steps.append({"name": "backup_project", "status": "completed", "backup_project_path": str(backup_project_path)})
    log_event("backup_project", "completed", backup_project_path=str(backup_project_path))

    context = {
        "schema_version": SCHEMA_VERSION,
        "status": "running",
        "profile_id": PROFILE_ID,
        "afd_path": str(resolved_afd),
        "material_path": str(resolved_material),
        "material_grade": material_grade,
        "material_temper": material_temper,
        "project_resolution": project_resolution,
        "save_project": save_project,
        "dry_run": dry_run,
        "backup_dir": str(backup_dir.resolve()),
        "backup_project_path": str(backup_project_path.resolve()),
        "before_summary": before_summary,
        "before_material_fragments": before_fragments,
        "material_info": material_info,
        "run_dir": str(run_dir.resolve()),
        "evidence_dir": str(evidence_dir.resolve()),
        "screenshots": screenshots,
        "window_trees": window_trees,
        "logs": logs,
        "steps": steps,
        "started_at": started_at,
    }

    if dry_run:
        planned = {
            **context,
            "status": "planned",
            "steps": [
                *steps,
                {"name": "open_or_focus_project", "status": "planned"},
                {"name": "open_material_page", "status": "planned"},
                {"name": "add_material", "status": "planned"},
                {"name": "save_project", "status": "planned" if save_project else "skipped"},
                {"name": "verify_material_change", "status": "planned"},
            ],
            "material_changed": False,
            "finished_at": _utc_now(),
        }
        _write_manifest(evidence_dir, planned, logs)
        return planned

    try:
        sequence_result = _run_gui_material_assignment_sequence(
            afd_path=resolved_afd,
            material_path=resolved_material,
            evidence_dir=evidence_dir,
            screenshots=screenshots,
            window_trees=window_trees,
            steps=steps,
            log_event=log_event,
            graphics=graphics,
            gui_wait_seconds=gui_wait_seconds,
            save_project=save_project,
        )
    except Exception as exc:
        _capture_evidence(
            evidence_dir=evidence_dir,
            screenshots=screenshots,
            window_trees=window_trees,
            name="99_failed",
            steps=steps,
            log_event=log_event,
            wait_seconds=0.2,
        )
        failed = {
            **context,
            "status": "failed",
            "failure_reason": str(exc),
            "finished_at": _utc_now(),
        }
        _write_manifest(evidence_dir, failed, logs)
        return failed

    after_summary = _safe_afd_summary(resolved_afd)
    after_fragments = _safe_afd_material_fragments(resolved_afd)
    material_changed = _material_assignment_verified(
        before_summary=before_summary,
        after_summary=after_summary,
        before_fragments=before_fragments,
        after_fragments=after_fragments,
        material_path=resolved_material,
    )
    verify_status = "completed" if material_changed else "blocked_verification_failed"
    steps.append(
        {
            "name": "verify_material_change",
            "status": verify_status,
            "material_changed": material_changed,
        }
    )
    log_event("verify_material_change", verify_status, material_changed=material_changed)
    status = "completed" if material_changed else "blocked_verification_failed"
    result = {
        **context,
        **sequence_result,
        "status": status,
        "after_summary": after_summary,
        "after_material_fragments": after_fragments,
        "material_changed": material_changed,
        "blocked_reason": "" if material_changed else "Saved project material fields did not show a verified material change.",
        "finished_at": _utc_now(),
    }
    _write_manifest(evidence_dir, result, logs)
    return result


def resolve_assignment_project_path(
    afd_path: str | None,
    *,
    project_resolution: str = "current_or_prompt",
    project_root: str | Path | None = None,
    search_roots: list[str | Path] | None = None,
) -> Path:
    """Resolve the project that should receive material assignment."""

    if afd_path:
        path = Path(_strip_path_text(afd_path)).expanduser().resolve()
        if not path.exists():
            raise ProjectResolutionError(f"afd_path does not exist: {path}")
        if path.suffix.casefold() != ".afd":
            raise ProjectResolutionError(f"afd_path must end with .afd: {path}")
        return path

    if project_resolution not in {"current_or_prompt", "gui_title"}:
        raise ProjectResolutionError(f"unsupported project_resolution: {project_resolution}")

    snapshot = autoform_window_snapshot()
    title_candidates = _afd_names_from_window_snapshot(snapshot)
    roots = _project_search_roots(project_root=project_root, search_roots=search_roots)
    matches: list[Path] = []
    for name in title_candidates:
        matches.extend(_find_afd_by_name(name, roots))
    unique = _unique_paths(matches)
    if len(unique) == 1:
        return unique[0]
    if len(unique) > 1:
        raise AmbiguousProjectError("current GUI project name matched multiple .afd files.", unique)
    raise ProjectResolutionError("No explicit .afd path or uniquely matched current AutoForm GUI project was found.")


def resolve_assignment_material_path(
    material_path: str | None,
    *,
    project_root: str | Path | None = None,
    materials_root: str | Path | None = None,
) -> Path:
    """Resolve and validate the material file used for assignment."""

    if not material_path:
        raise MaterialResolutionError("material_path is required when no MaterialCard source is supplied.")
    raw = _strip_path_text(material_path)
    direct = Path(raw).expanduser()
    candidates: list[Path] = []
    if direct.is_absolute():
        candidates.append(direct.resolve())
    else:
        root = Path(project_root or Path.cwd()).resolve()
        candidates.append((root / direct).resolve())
        if materials_root is not None:
            candidates.extend(_find_material_by_name(direct.name, [Path(materials_root).resolve()]))
        else:
            try:
                candidates.extend(_find_material_by_name(direct.name, [get_default_installation().materials_dir]))
            except Exception:
                pass

    existing = _unique_paths([candidate for candidate in candidates if candidate.exists()])
    if len(existing) > 1:
        raise AmbiguousMaterialError("material file name matched multiple candidates.", existing)
    if not existing:
        raise MaterialResolutionError(f"material_path does not exist: {raw}")
    path = existing[0]
    if not path.is_file():
        raise MaterialResolutionError(f"material_path must be a file: {path}")
    if path.suffix.casefold() not in SUPPORTED_MATERIAL_SUFFIXES:
        raise MaterialResolutionError(f"unsupported material file extension: {path.suffix}")
    return path


def extract_material_path_from_text(text: str, *, project_root: str | Path | None = None) -> str:
    """Extract a `.mtb` or `.mat` path or filename from prompt text."""

    prompt = str(text or "")
    if not prompt.strip():
        return ""
    suffix_pattern = r"(?:mtb|mat)"
    patterns = (
        rf'"([^"\r\n]+?\.{suffix_pattern})"',
        rf"'([^'\r\n]+?\.{suffix_pattern})'",
        rf"`([^`\r\n]+?\.{suffix_pattern})`",
        rf"([A-Za-z]:[^\r\n\"'`<>|]*?\.{suffix_pattern})",
        rf"(\\\\[^\r\n\"'`<>|]*?\.{suffix_pattern})",
        rf"([^\s\\/:*?\"<>|]+?\.{suffix_pattern})",
    )
    for pattern in patterns:
        match = re.search(pattern, prompt, flags=re.IGNORECASE)
        if not match:
            continue
        candidate = next((group for group in match.groups() if group), "")
        candidate = _strip_path_text(candidate)
        if not candidate:
            continue
        try:
            return str(resolve_assignment_material_path(candidate, project_root=project_root))
        except MaterialResolutionError:
            if Path(candidate).suffix.casefold() in SUPPORTED_MATERIAL_SUFFIXES:
                return candidate
        except AmbiguousMaterialError:
            return candidate
    return ""


class ProjectResolutionError(ValueError):
    """Raised when an assignment target project cannot be resolved."""


class MaterialResolutionError(ValueError):
    """Raised when an assignment material file cannot be resolved."""


class AmbiguousProjectError(ProjectResolutionError):
    """Raised when multiple `.afd` files match the current GUI title."""

    def __init__(self, message: str, candidates: list[Path]) -> None:
        super().__init__(message)
        self.candidates = [str(path) for path in candidates]


class AmbiguousMaterialError(MaterialResolutionError):
    """Raised when multiple material files match a material filename."""

    def __init__(self, message: str, candidates: list[Path]) -> None:
        super().__init__(message)
        self.candidates = [str(path) for path in candidates]


def _run_gui_material_assignment_sequence(
    *,
    afd_path: Path,
    material_path: Path,
    evidence_dir: Path,
    screenshots: list[str],
    window_trees: list[str],
    steps: list[dict[str, Any]],
    log_event,
    graphics: str,
    gui_wait_seconds: float,
    save_project: bool,
) -> dict[str, Any]:
    gui_observation = open_afd_observer(afd_path, dry_run=False)
    steps.append({"name": "open_or_focus_project", "status": "completed", "evidence": gui_observation})
    log_event("open_or_focus_project", "completed", evidence=gui_observation)
    time.sleep(max(float(gui_wait_seconds), 0))

    _capture_evidence(
        evidence_dir=evidence_dir,
        screenshots=screenshots,
        window_trees=window_trees,
        name="01_before_assignment",
        steps=steps,
        log_event=log_event,
        title_contains=afd_path.name,
        wait_seconds=0.2,
    )

    material_page = _open_material_page(afd_path=afd_path, log_event=log_event)
    steps.append({"name": "open_material_page", "status": material_page.get("status"), "evidence": material_page})
    if str(material_page.get("status")).startswith("blocked"):
        return {"gui_observation": gui_observation, "profile_actions": [material_page], "blocked_reason": "material_page_not_reached"}

    add = _click_add_material(afd_path=afd_path, log_event=log_event)
    steps.append({"name": "add_material", "status": add.get("status"), "evidence": add})
    if str(add.get("status")).startswith("blocked"):
        return {"gui_observation": gui_observation, "profile_actions": [material_page, add], "blocked_reason": "add_material_control_not_found"}

    pasted = paste_text_to_autoform(str(material_path), focus_first=False, restore_window=False, wait_seconds=0.1)
    entered = send_autoform_keystroke("enter", focus_first=False, wait_seconds=0.2)
    time.sleep(1.0)
    steps.append({"name": "select_material_file", "status": "completed" if pasted.get("pasted") else "failed", "paste": pasted, "enter": entered})
    log_event("select_material_file", "completed" if pasted.get("pasted") else "failed", paste=pasted, enter=entered)

    if save_project:
        save = send_autoform_keystroke("control+s", title_contains=afd_path.name, focus_first=True, restore_window=True, wait_seconds=0.3)
        steps.append({"name": "save_project", "status": "completed" if save.get("sent") else "failed", "evidence": save})
        log_event("save_project", "completed" if save.get("sent") else "failed", evidence=save)
        time.sleep(2.0)
    else:
        steps.append({"name": "save_project", "status": "skipped", "reason": "save_project_false"})
        log_event("save_project", "skipped", reason="save_project_false")

    _capture_evidence(
        evidence_dir=evidence_dir,
        screenshots=screenshots,
        window_trees=window_trees,
        name="02_after_assignment",
        steps=steps,
        log_event=log_event,
        title_contains=afd_path.name,
        wait_seconds=0.2,
    )
    return {"gui_observation": gui_observation, "profile_actions": [material_page, add], "blocked_reason": ""}


def _open_material_page(*, afd_path: Path, log_event) -> dict[str, Any]:
    # These shortcuts/clicks are profile actions for R13. They are intentionally
    # audited and followed by control-tree inspection rather than trusted blindly.
    focus = focus_autoform_window(title_contains=afd_path.name, restore_window=True)
    shortcut = send_autoform_keystroke("control+1", title_contains=afd_path.name, focus_first=False, wait_seconds=0.2)
    fallback_click = click_autoform_window(0.06, 0.32, title_contains=afd_path.name, restore_window=True, wait_seconds=0.2)
    time.sleep(0.8)
    tree = autoform_window_tree_snapshot(title_contains=afd_path.name, max_children=600)
    reached = _tree_has_material_page(tree)
    status = "completed" if reached else "attempted"
    result = {"status": status, "focus": focus, "shortcut": shortcut, "fallback_click": fallback_click, "tree_status": tree.get("status")}
    log_event("open_material_page", status, evidence=result)
    return result


def _click_add_material(*, afd_path: Path, log_event) -> dict[str, Any]:
    tree = autoform_window_tree_snapshot(title_contains=afd_path.name, max_children=800)
    control = _find_material_add_control(tree)
    if control:
        rect = control.get("rect") or {}
        screen_x = int(rect.get("left", 0) + max(rect.get("width", 0), 1) / 2)
        screen_y = int(rect.get("top", 0) + max(rect.get("height", 0), 1) / 2)
        clicked = click_autoform_window(screen_x, screen_y, relative=False, title_contains=afd_path.name, restore_window=True, wait_seconds=0.2)
        status = "completed" if clicked.get("clicked") else "blocked_click_failed"
        result = {"status": status, "strategy": "window_tree_control", "control": control, "click": clicked}
        log_event("click_add_material", status, evidence=result)
        return result
    fallback = click_autoform_window(0.82, 0.24, relative=True, title_contains=afd_path.name, restore_window=True, wait_seconds=0.2)
    status = "completed" if fallback.get("clicked") else "blocked_no_add_material_control"
    result = {"status": status, "strategy": "r13_relative_fallback", "click": fallback}
    log_event("click_add_material", status, evidence=result)
    return result


def _capture_evidence(
    *,
    evidence_dir: Path,
    screenshots: list[str],
    window_trees: list[str],
    name: str,
    steps: list[dict[str, Any]],
    log_event,
    wait_seconds: float,
    title_contains: str | None = None,
) -> None:
    screenshot_path = evidence_dir / f"{name}.png"
    tree_path = evidence_dir / f"{name}_window_tree.json"
    capture = capture_desktop_screenshot(
        screenshot_path,
        focus_autoform=True,
        title_contains=title_contains,
        wait_seconds=wait_seconds,
        restore_window=False,
    )
    tree = autoform_window_tree_snapshot(title_contains=title_contains, max_children=800)
    tree_path.write_text(json.dumps(tree, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    screenshots.append(str(screenshot_path.resolve()))
    window_trees.append(str(tree_path.resolve()))
    steps.append({"name": f"capture_{name}", "status": "completed", "screenshot": capture, "window_tree": str(tree_path)})
    log_event(f"capture_{name}", "completed", screenshot=capture, window_tree=str(tree_path))


def _material_assignment_verified(
    *,
    before_summary: dict[str, Any],
    after_summary: dict[str, Any],
    before_fragments: dict[str, Any],
    after_fragments: dict[str, Any],
    material_path: Path,
) -> bool:
    before_material = before_summary.get("material") if isinstance(before_summary.get("material"), dict) else {}
    after_material = after_summary.get("material") if isinstance(after_summary.get("material"), dict) else {}
    if before_material != after_material and _material_name_matches(after_material, material_path):
        return True
    before_text = json.dumps(before_fragments, ensure_ascii=False)
    after_text = json.dumps(after_fragments, ensure_ascii=False)
    material_stem = material_path.stem.casefold()
    return before_text != after_text and material_stem in after_text.casefold()


def _material_name_matches(material: dict[str, Any], material_path: Path) -> bool:
    material_stem = material_path.stem.casefold()
    material_name = str(material.get("name") or material.get("string") or "").casefold()
    if not material_name:
        return False
    return material_stem in material_name or material_name in material_stem


def _safe_afd_summary(path: Path) -> dict[str, Any]:
    try:
        return get_afd_project_summary(path)
    except Exception as exc:
        return {"source": "afd_project_summary_failed", "path": str(path), "error_type": type(exc).__name__, "error": str(exc)}


def _safe_afd_material_fragments(path: Path) -> dict[str, Any]:
    try:
        return get_afd_readable_index(path, query="Material", limit=80)
    except Exception as exc:
        return {"source": "afd_material_fragments_failed", "path": str(path), "error_type": type(exc).__name__, "error": str(exc)}


def _tree_has_material_page(tree: dict[str, Any]) -> bool:
    return _find_material_add_control(tree) is not None or _tree_contains_any(
        tree,
        ("MaterialPagePresenter", "AddMaterialEditor", "Add Material", "MaterialSubPresenter"),
    )


def _find_material_add_control(tree: dict[str, Any]) -> dict[str, Any] | None:
    children = tree.get("children") if isinstance(tree.get("children"), list) else []
    needles = ("MaterialPagePresenter[Add Material]", "Add Material", "AddMaterialEditor")
    for child in children:
        haystack = f"{child.get('title') or ''} {child.get('class_name') or ''}"
        if any(needle.casefold() in haystack.casefold() for needle in needles):
            rect = child.get("rect") if isinstance(child.get("rect"), dict) else {}
            if int(rect.get("width") or 0) > 0 and int(rect.get("height") or 0) > 0:
                return child
    return None


def _tree_contains_any(tree: dict[str, Any], needles: tuple[str, ...]) -> bool:
    text = json.dumps(tree, ensure_ascii=False)
    lowered = text.casefold()
    return any(needle.casefold() in lowered for needle in needles)


def _afd_names_from_window_snapshot(snapshot: dict[str, Any]) -> list[str]:
    windows = snapshot.get("interaction_ready_windows") or snapshot.get("windows") or []
    names: list[str] = []
    for window in windows if isinstance(windows, list) else []:
        title = str(window.get("title") or "")
        for match in re.finditer(r"([^\\/:*?\"<>|\r\n]+?\.afd)", title, flags=re.IGNORECASE):
            candidate = match.group(1).strip()
            basename = Path(candidate).name
            if basename == candidate:
                tail = re.search(r"([^\s\\/:*?\"<>|]+\.afd)$", candidate, flags=re.IGNORECASE)
                if tail:
                    basename = tail.group(1).strip()
            names.append(basename)
    return list(dict.fromkeys(names))


def _project_search_roots(
    *,
    project_root: str | Path | None,
    search_roots: list[str | Path] | None,
) -> list[Path]:
    roots = [Path(item).resolve() for item in search_roots or []]
    root = Path(project_root or Path.cwd()).resolve()
    roots.extend([root, root / "output", root / "outputs"])
    try:
        roots.append(get_default_installation().test_dir)
    except Exception:
        pass
    return _unique_paths([item for item in roots if item.exists()])


def _find_afd_by_name(name: str, roots: list[Path]) -> list[Path]:
    matches: list[Path] = []
    for root in roots:
        try:
            matches.extend(path.resolve() for path in root.rglob(name) if path.is_file())
        except Exception:
            continue
    return matches


def _find_material_by_name(name: str, roots: list[Path]) -> list[Path]:
    matches: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        try:
            matches.extend(path.resolve() for path in root.rglob(name) if path.is_file())
        except Exception:
            continue
    return matches


def _unique_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = str(path).casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _run_dir(output_dir: Path, seed: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = _safe_stem(Path(_strip_path_text(seed)).stem or "material_assignment")
    candidate = (output_dir / f"{timestamp}_{stem}").resolve()
    index = 1
    while candidate.exists():
        candidate = (output_dir / f"{timestamp}_{stem}_{index}").resolve()
        index += 1
    return candidate


def _backup_dir(backup_root: Path, afd_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return (backup_root / f"{timestamp}_{_safe_stem(afd_path.stem)}").resolve()


def _safe_stem(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.\-\u4e00-\u9fff]+", "_", value).strip("._")
    return cleaned[:80] or "item"


def _strip_path_text(value: str | Path | None) -> str:
    return str(value or "").strip().strip("\"'`“”‘’").strip("，,。；;、）)]}>\u3000 ")


def _write_manifest(evidence_dir: Path, result: dict[str, Any], logs: list[str]) -> None:
    manifest_path = evidence_dir / "manifest.json"
    manifest_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    manifest_str = str(manifest_path.resolve())
    if manifest_str not in logs:
        logs.append(manifest_str)
    result["logs"] = logs


def _blocked_result(
    *,
    status: str,
    blocked_reason: str,
    started_at: str,
    run_dir: Path,
    evidence_dir: Path,
    logs: list[str],
    steps: list[dict[str, Any]],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "blocked_reason": blocked_reason,
        "run_dir": str(run_dir.resolve()),
        "evidence_dir": str(evidence_dir.resolve()),
        "logs": logs,
        "steps": steps,
        "material_changed": False,
        "started_at": started_at,
        "finished_at": _utc_now(),
        **(extra or {}),
    }
    _write_manifest(evidence_dir, result, logs)
    return result


def _failed_result(
    *,
    failure_reason: str,
    started_at: str,
    run_dir: Path,
    evidence_dir: Path,
    logs: list[str],
    steps: list[dict[str, Any]],
) -> dict[str, Any]:
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "failed",
        "failure_reason": failure_reason,
        "run_dir": str(run_dir.resolve()),
        "evidence_dir": str(evidence_dir.resolve()),
        "logs": logs,
        "steps": steps,
        "material_changed": False,
        "started_at": started_at,
        "finished_at": _utc_now(),
    }
    _write_manifest(evidence_dir, result, logs)
    return result


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "DEFAULT_BACKUP_ROOT",
    "DEFAULT_OUTPUT_ROOT",
    "PROFILE_ID",
    "SCHEMA_VERSION",
    "assign_material_to_project",
    "extract_material_path_from_text",
    "resolve_assignment_material_path",
    "resolve_assignment_project_path",
]
