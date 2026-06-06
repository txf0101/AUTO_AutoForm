"""Registry loader for stable SkillCards and legacy low-risk rows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .contracts import (
    EXECUTABLE_RISK_LEVELS,
    FLEX_SKILLS_ROOT,
    LEGACY_SCRIPT_REGISTRY,
    ROOT,
    SkillRecord,
)


def catalog_scripts(
    *,
    query: str | None = None,
    skill_id: str | None = None,
    risk_level: str | None = None,
    include_legacy: bool = False,
) -> dict[str, Any]:
    """Return discoverable script skills with optional legacy rows."""

    rows = [
        record.as_catalog_row()
        for record in load_skill_records(include_legacy=include_legacy)
        if _matches(record, query=query, skill_id=skill_id, risk_level=risk_level)
    ]
    rows.sort(key=lambda item: (item["source"], item["skill_id"], item["skill_version"]))
    return {
        "schema_version": "autoform.script_catalog.v1",
        "status": "completed",
        "query": query or "",
        "skill_id": skill_id or "",
        "risk_level": risk_level or "",
        "include_legacy": include_legacy,
        "count": len(rows),
        "skills": rows,
    }


def get_registered_skill(
    skill_id: str,
    *,
    skill_version: str | None = None,
    allow_legacy: bool = False,
) -> SkillRecord | None:
    candidates = [
        record
        for record in load_skill_records(include_legacy=allow_legacy)
        if record.skill_id == skill_id and (not skill_version or record.skill_version == skill_version)
    ]
    stable = [record for record in candidates if record.source == "stable_library"]
    if stable:
        return sorted(stable, key=lambda item: item.skill_version)[-1]
    return candidates[0] if candidates else None


def load_skill_records(*, include_legacy: bool = False) -> list[SkillRecord]:
    records = _load_stable_skill_cards(FLEX_SKILLS_ROOT)
    if include_legacy:
        records.extend(_load_legacy_registry(LEGACY_SCRIPT_REGISTRY))
    return records


def _load_stable_skill_cards(skills_root: Path) -> list[SkillRecord]:
    if not skills_root.exists():
        return []
    records: list[SkillRecord] = []
    for card_path in sorted(skills_root.glob("*/skill_card.yaml")):
        data = _parse_simple_yaml(card_path)
        skill_id = str(data.get("skill_id") or card_path.parent.name).strip()
        version = str(data.get("skill_version") or "v1").strip()
        entrypoint_raw = str(data.get("entrypoint") or "").strip()
        entrypoint = (ROOT / entrypoint_raw).resolve() if entrypoint_raw else None
        records.append(
            SkillRecord(
                skill_id=skill_id,
                skill_version=version,
                title=str(data.get("title") or skill_id),
                description=str(data.get("description") or ""),
                risk_level=str(data.get("risk_level") or "L1"),
                entrypoint=entrypoint,
                source="stable_library",
                required_params=_split_field(data.get("required_params")),
                allowed_params=_split_field(data.get("allowed_params")),
                tags=_split_field(data.get("tags")),
                skill_card_path=card_path.resolve(),
                stable=True,
            )
        )
    return records


def _load_legacy_registry(path: Path) -> list[SkillRecord]:
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("- "):
            if current:
                entries.append(current)
            current = {}
            key, value = _split_yaml_pair(line[2:])
            current[key] = _yaml_value(value)
        elif current is not None and ":" in line:
            key, value = _split_yaml_pair(line.strip())
            current[key] = _yaml_value(value)
    if current:
        entries.append(current)
    records: list[SkillRecord] = []
    for item in entries:
        skill_id = str(item.get("skill_id") or "").strip()
        if not skill_id:
            continue
        records.append(
            SkillRecord(
                skill_id=skill_id,
                skill_version=str(item.get("skill_version") or "legacy"),
                title=str(item.get("title") or skill_id),
                description=str(item.get("description") or ""),
                risk_level=str(item.get("risk_level") or "L1"),
                entrypoint=None,
                source="legacy_registry",
                required_params=_split_field(item.get("required_params")),
                allowed_params=_split_field(item.get("allowed_params") or item.get("required_params")),
                tags=("legacy",),
                skill_card_path=path.resolve(),
                stable=False,
            )
        )
    return records


def _parse_simple_yaml(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = _split_yaml_pair(line)
        data[key] = _yaml_value(value)
    return data


def _split_yaml_pair(line: str) -> tuple[str, str]:
    key, value = line.split(":", 1)
    return key.strip(), value.strip()


def _yaml_value(value: str) -> Any:
    cleaned = value.strip()
    if (cleaned.startswith('"') and cleaned.endswith('"')) or (cleaned.startswith("'") and cleaned.endswith("'")):
        return cleaned[1:-1]
    if cleaned.lower() == "true":
        return True
    if cleaned.lower() == "false":
        return False
    return cleaned


def _split_field(value: Any) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return tuple(item.strip() for item in str(value or "").replace(",", ";").split(";") if item.strip())


def _matches(
    record: SkillRecord,
    *,
    query: str | None,
    skill_id: str | None,
    risk_level: str | None,
) -> bool:
    if skill_id and record.skill_id != skill_id:
        return False
    if risk_level and record.risk_level != risk_level:
        return False
    if not query:
        return True
    needle = query.casefold()
    haystack = " ".join(
        [
            record.skill_id,
            record.title,
            record.description,
            record.risk_level,
            " ".join(record.tags),
        ]
    ).casefold()
    return needle in haystack


def is_executable_low_risk(record: SkillRecord) -> bool:
    return record.source == "stable_library" and record.risk_level in EXECUTABLE_RISK_LEVELS and record.entrypoint is not None
