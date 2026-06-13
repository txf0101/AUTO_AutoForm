"""Static safety checks for sandboxed flexible scripts."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from .contracts import STATIC_AUDIT_SCHEMA_VERSION, utc_now


BLOCKED_IMPORT_ROOTS = {
    "ctypes",
    "ftplib",
    "http",
    "paramiko",
    "requests",
    "socket",
    "subprocess",
    "telnetlib",
    "urllib",
    "webbrowser",
    "winreg",
}
BLOCKED_CALL_NAMES = {"eval", "exec", "compile", "__import__"}
BLOCKED_ATTR_CALLS = {
    ("os", "system"),
    ("os", "popen"),
    ("subprocess", "run"),
    ("subprocess", "Popen"),
    ("subprocess", "call"),
    ("subprocess", "check_call"),
    ("subprocess", "check_output"),
}


def audit_python_file(path: str | Path) -> dict[str, Any]:
    """Audit one Python script and return a machine-readable report."""

    script_path = Path(path).resolve()
    if not script_path.exists():
        return _report("failed", str(script_path), [{"name": "file_exists", "status": "failed", "detail": "missing"}])
    try:
        tree = ast.parse(script_path.read_text(encoding="utf-8"), filename=str(script_path))
    except SyntaxError as exc:
        return _report(
            "failed",
            str(script_path),
            [{"name": "ast_parse", "status": "failed", "line": exc.lineno, "detail": str(exc)}],
        )

    checks: list[dict[str, Any]] = [{"name": "ast_parse", "status": "passed"}]
    blocked_imports = _blocked_imports(tree)
    blocked_calls = _blocked_calls(tree)
    suspicious_writes = _suspicious_writes(tree)
    checks.append(
        {
            "name": "blocked_imports",
            "status": "failed" if blocked_imports else "passed",
            "blocked": blocked_imports,
        }
    )
    checks.append(
        {
            "name": "blocked_calls",
            "status": "failed" if blocked_calls else "passed",
            "blocked": blocked_calls,
        }
    )
    checks.append(
        {
            "name": "suspicious_writes",
            "status": "warning" if suspicious_writes else "passed",
            "writes": suspicious_writes,
        }
    )
    status = "failed" if blocked_imports or blocked_calls else "passed"
    return _report(status, str(script_path), checks)


def audit_python_tree(root: str | Path) -> dict[str, Any]:
    """Audit every Python file under a sandbox tree."""

    base = Path(root).resolve()
    files = sorted(base.rglob("*.py")) if base.exists() else []
    audits = [audit_python_file(path) for path in files]
    status = "passed" if audits and all(item.get("status") == "passed" for item in audits) else "failed"
    if not audits:
        status = "failed"
    return {
        "schema_version": STATIC_AUDIT_SCHEMA_VERSION,
        "object_type": "ScriptStaticAudit",
        "status": status,
        "root": str(base),
        "file_count": len(audits),
        "files": audits,
        "created_at": utc_now(),
    }


def _blocked_imports(tree: ast.AST) -> list[dict[str, Any]]:
    blocked: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in BLOCKED_IMPORT_ROOTS:
                    blocked.append({"name": alias.name, "line": node.lineno})
        elif isinstance(node, ast.ImportFrom):
            root = str(node.module or "").split(".", 1)[0]
            if root in BLOCKED_IMPORT_ROOTS:
                blocked.append({"name": str(node.module or root), "line": node.lineno})
    return blocked


def _blocked_calls(tree: ast.AST) -> list[dict[str, Any]]:
    blocked: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node.func)
        if name in BLOCKED_CALL_NAMES:
            blocked.append({"name": name, "line": node.lineno})
            continue
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            pair = (node.func.value.id, node.func.attr)
            if pair in BLOCKED_ATTR_CALLS:
                blocked.append({"name": ".".join(pair), "line": node.lineno})
    return blocked


def _suspicious_writes(tree: ast.AST) -> list[dict[str, Any]]:
    writes: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in {"write_text", "write_bytes", "open"}:
            continue
        writes.append({"name": _call_name(node.func), "line": getattr(node, "lineno", None)})
    return writes


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _report(status: str, path: str, checks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": STATIC_AUDIT_SCHEMA_VERSION,
        "object_type": "ScriptStaticAudit",
        "status": status,
        "script_path": path,
        "checks": checks,
        "created_at": utc_now(),
    }
