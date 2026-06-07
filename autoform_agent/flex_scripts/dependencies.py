"""Dependency probes for flexible scripts and CAD parsers."""

from __future__ import annotations

import ast
import importlib.util
import shutil
import sys
from pathlib import Path
from typing import Any

from .contracts import DEPENDENCY_REPORT_SCHEMA_VERSION, ROOT, utc_now


LOCAL_IMPORT_ROOTS = {"autoform_agent", "flex_script_library", "scripts"}
CAD_PARSER_MODULES = ("cadquery", "OCP", "OCC", "meshio", "trimesh")
CAD_PARSER_COMMANDS = ("FreeCADCmd", "FreeCAD")


def probe_script_dependencies(path: str | Path) -> dict[str, Any]:
    """Return a deterministic dependency report for one Python script."""

    script_path = Path(path).resolve()
    imports = _imports_from_python(script_path)
    rows = []
    for name in imports:
        rows.append(_dependency_row(name))
    status = "passed" if all(row["available"] for row in rows) else "blocked"
    return {
        "schema_version": DEPENDENCY_REPORT_SCHEMA_VERSION,
        "object_type": "ScriptDependencyReport",
        "status": status,
        "script_path": str(script_path),
        "imports": rows,
        "install_hint": _install_hint(rows),
        "created_at": utc_now(),
    }


def probe_cad_parsers() -> dict[str, Any]:
    """Probe local STEP/IGES parser candidates without importing heavy modules."""

    modules = {name: _module_probe(name) for name in CAD_PARSER_MODULES}
    commands = {name: _command_probe(name) for name in CAD_PARSER_COMMANDS}
    available = [name for name, row in {**modules, **commands}.items() if row.get("available")]
    return {
        "schema_version": "autoform.cad_parser_probe.v1",
        "object_type": "CadParserProbe",
        "status": "completed" if available else "blocked",
        "available_parsers": available,
        "modules": modules,
        "commands": commands,
        "preferred_order": ["cadquery", "FreeCADCmd", "FreeCAD", "OCP", "OCC", "meshio", "trimesh"],
        "install_hints": {
            "cadquery": f"{Path(sys.executable).name} -m pip install cadquery",
            "freecadcmd": "Install FreeCAD and make FreeCADCmd.exe visible on PATH.",
        },
        "created_at": utc_now(),
    }


def _imports_from_python(path: Path) -> list[str]:
    if not path.exists() or path.suffix.casefold() != ".py":
        return []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root:
                    names.add(root)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            root = str(node.module or "").split(".", 1)[0]
            if root:
                names.add(root)
    return sorted(names)


def _dependency_row(name: str) -> dict[str, Any]:
    if name in sys.builtin_module_names or name in getattr(sys, "stdlib_module_names", set()):
        return {"name": name, "kind": "stdlib", "available": True, "origin": "python-stdlib"}
    if name in LOCAL_IMPORT_ROOTS:
        return {"name": name, "kind": "workspace", "available": (ROOT / name).exists(), "origin": str(ROOT / name)}
    probe = _module_probe(name)
    return {"name": name, "kind": "third_party", **probe}


def _module_probe(name: str) -> dict[str, Any]:
    try:
        spec = importlib.util.find_spec(name)
        return {"available": bool(spec), "origin": spec.origin if spec and spec.origin else ""}
    except Exception as exc:
        return {"available": False, "origin": "", "error": f"{exc.__class__.__name__}: {exc}"}


def _command_probe(name: str) -> dict[str, Any]:
    path = shutil.which(name)
    return {"available": bool(path), "path": path or ""}


def _install_hint(rows: list[dict[str, Any]]) -> str:
    missing = [row["name"] for row in rows if row.get("kind") == "third_party" and not row.get("available")]
    if not missing:
        return ""
    return f"{Path(sys.executable).name} -m pip install {' '.join(missing)}"
