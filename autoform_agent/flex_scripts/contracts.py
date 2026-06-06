"""Shared contracts and filesystem boundaries for flexible scripts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
FLEX_LIBRARY_ROOT = ROOT / "flex_script_library"
FLEX_SKILLS_ROOT = FLEX_LIBRARY_ROOT / "skills"
FLEX_SANDBOX_ROOT = ROOT / "tmp" / "flex_script_sandbox"
SCRIPT_RUN_OUTPUT_ROOT = ROOT / "output" / "script_runs"
CAD_MEASUREMENT_OUTPUT_ROOT = ROOT / "output" / "cad_measurements"
LEGACY_SCRIPT_REGISTRY = ROOT / "script_registry.yaml"

SCRIPT_RUN_SCHEMA_VERSION = "autoform.script_run_record.v1"
SKILL_CARD_SCHEMA_VERSION = "autoform.skill_card.v1"
VALIDATION_REPORT_SCHEMA_VERSION = "autoform.script_validation_report.v1"
CAD_MEASUREMENT_SCHEMA_VERSION = "autoform.cad_measurement_result.v1"

ALLOWED_RISK_LEVELS = {"L0", "L1", "L2", "L3", "L4"}
EXECUTABLE_RISK_LEVELS = {"L0", "L1"}
MAX_CAPTURE_CHARS = 12000
DEFAULT_TIMEOUT_SECONDS = 60


@dataclass(frozen=True)
class SkillRecord:
    """One stable or legacy script registry row."""

    skill_id: str
    skill_version: str
    title: str
    description: str
    risk_level: str
    entrypoint: Path | None
    source: str
    required_params: tuple[str, ...] = ()
    allowed_params: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    skill_card_path: Path | None = None
    stable: bool = True

    def as_catalog_row(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "skill_version": self.skill_version,
            "title": self.title,
            "description": self.description,
            "risk_level": self.risk_level,
            "entrypoint": str(self.entrypoint) if self.entrypoint else "",
            "source": self.source,
            "required_params": list(self.required_params),
            "allowed_params": list(self.allowed_params),
            "tags": list(self.tags),
            "skill_card_path": str(self.skill_card_path) if self.skill_card_path else "",
            "stable": self.stable,
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def timestamp_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def slug(value: str, *, default: str = "item", limit: int = 80) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z_.-]+", "_", str(value or default)).strip("._- ")
    return (cleaned or default)[:limit]


def params_hash(params: dict[str, Any]) -> str:
    payload = json.dumps(params or {}, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_workspace_dirs() -> None:
    for path in (
        FLEX_LIBRARY_ROOT,
        FLEX_SKILLS_ROOT,
        FLEX_SANDBOX_ROOT,
        SCRIPT_RUN_OUTPUT_ROOT,
        CAD_MEASUREMENT_OUTPUT_ROOT,
    ):
        path.mkdir(parents=True, exist_ok=True)


def ensure_under(parent: str | Path, child: str | Path) -> Path:
    parent_path = Path(parent).resolve()
    child_path = Path(child).resolve()
    if child_path != parent_path and parent_path not in child_path.parents:
        raise ValueError(f"path_outside_allowed_root: {child_path}")
    return child_path


def json_safe(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False, default=str)
        return value
    except TypeError:
        if isinstance(value, dict):
            return {str(key): json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [json_safe(item) for item in value]
        return str(value)


def write_json(path: str | Path, value: Any) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(json_safe(value), ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def read_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def truncate_text(value: str, *, limit: int = MAX_CAPTURE_CHARS) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[truncated {len(text) - limit} chars]"
