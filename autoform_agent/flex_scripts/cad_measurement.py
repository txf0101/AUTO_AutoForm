"""CAD geometry measurement helpers used by the first stable flex script."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import shutil
import struct
from typing import Any

from .contracts import (
    CAD_MEASUREMENT_OUTPUT_ROOT,
    CAD_MEASUREMENT_SCHEMA_VERSION,
    file_sha256,
    slug,
    timestamp_id,
    utc_now,
    write_json,
)


SUPPORTED_SUFFIXES = {".stl", ".step", ".stp", ".igs", ".iges"}


def measure_cad_geometry(
    source_geometry_path: str,
    *,
    length_unit: str = "mm",
    output_root: str | Path = CAD_MEASUREMENT_OUTPUT_ROOT,
) -> dict[str, Any]:
    """Measure CAD geometry when a first-stage local parser is available."""

    started_at = utc_now()
    source_path = Path(source_geometry_path).expanduser().resolve()
    run_dir = _measurement_run_dir(output_root, source_path)
    evidence_dir = run_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    log_path = evidence_dir / "cad_measurement_log.jsonl"

    def log_event(name: str, status: str, **payload: Any) -> None:
        record = {"time": utc_now(), "name": name, "status": status, **payload}
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    base = {
        "schema_version": CAD_MEASUREMENT_SCHEMA_VERSION,
        "object_type": "CadMeasurementResult",
        "status": "running",
        "source_geometry_path": str(source_path),
        "source_sha256": "",
        "parser": "",
        "unit": length_unit,
        "axis_aligned_bbox": None,
        "oriented_bbox": None,
        "length": None,
        "width": None,
        "thickness": None,
        "measurement_method": "",
        "confidence": "none",
        "evidence_dir": str(evidence_dir.resolve()),
        "logs": [str(log_path.resolve())],
        "failure_reason": "",
        "blocked_reason": "",
        "filename_dimension_candidate": _filename_dimension_candidate(source_path, length_unit=length_unit),
        "started_at": started_at,
        "finished_at": "",
    }

    try:
        _validate_source(source_path)
        base["source_sha256"] = file_sha256(source_path)
        log_event("validate_source", "completed", source=str(source_path), sha256=base["source_sha256"])
    except Exception as exc:
        result = {
            **base,
            "status": "failed",
            "parser": "validate_source",
            "failure_reason": str(exc),
            "finished_at": utc_now(),
        }
        log_event("validate_source", "failed", error_type=type(exc).__name__, error=str(exc))
        write_json(run_dir / "cad_measurement_result.json", result)
        return result

    suffix = source_path.suffix.casefold()
    try:
        if suffix == ".stl":
            result = _measure_stl(source_path, base=base, log_event=log_event)
        else:
            result = _blocked_probe_result(source_path, base=base, log_event=log_event)
    except Exception as exc:
        log_event("measure_geometry", "failed", error_type=type(exc).__name__, error=str(exc))
        result = {
            **base,
            "status": "failed",
            "parser": "stl_builtin" if suffix == ".stl" else "probe_only",
            "failure_reason": str(exc),
            "finished_at": utc_now(),
        }
    write_json(run_dir / "cad_measurement_result.json", result)
    return result


def _measure_stl(source_path: Path, *, base: dict[str, Any], log_event) -> dict[str, Any]:
    vertices = _read_stl_vertices(source_path)
    if not vertices:
        raise ValueError("STL file contains no vertex records")
    xs = [vertex[0] for vertex in vertices]
    ys = [vertex[1] for vertex in vertices]
    zs = [vertex[2] for vertex in vertices]
    mins = [min(xs), min(ys), min(zs)]
    maxs = [max(xs), max(ys), max(zs)]
    dims = [maxs[index] - mins[index] for index in range(3)]
    ordered = sorted(dims, reverse=True)
    log_event("stl_bbox", "completed", vertex_count=len(vertices), dimensions=dims)
    return {
        **base,
        "status": "completed",
        "parser": "stl_builtin",
        "axis_aligned_bbox": {
            "min": [_round_float(value) for value in mins],
            "max": [_round_float(value) for value in maxs],
            "dimensions": [_round_float(value) for value in dims],
        },
        "oriented_bbox": {"status": "not_computed", "reason": "first_stage_axis_aligned_bbox_only"},
        "length": _round_float(ordered[0]),
        "width": _round_float(ordered[1]),
        "thickness": _round_float(ordered[2]),
        "measurement_method": "stl_vertex_axis_aligned_bbox",
        "confidence": "medium",
        "finished_at": utc_now(),
    }


def _blocked_probe_result(source_path: Path, *, base: dict[str, Any], log_event) -> dict[str, Any]:
    probe = probe_step_iges_parsers()
    log_event("parser_probe", "blocked", probe=probe)
    blocked_reason = (
        "No STEP/IGES parser is available in the current environment. "
        "Install or expose FreeCADCmd, FreeCAD, OCP/OCC, meshio, or another verified CAD parser before measurement."
    )
    return {
        **base,
        "status": "blocked",
        "parser": "probe_only",
        "measurement_method": "parser_probe_only",
        "confidence": "none",
        "blocked_reason": blocked_reason,
        "parser_probe": probe,
        "finished_at": utc_now(),
    }


def probe_step_iges_parsers() -> dict[str, Any]:
    return {
        "FreeCADCmd": _command_probe("FreeCADCmd"),
        "FreeCAD": _command_probe("FreeCAD"),
        "OCP": _module_probe("OCP"),
        "OCC": _module_probe("OCC"),
        "meshio": _module_probe("meshio"),
        "trimesh": _module_probe("trimesh"),
        "autoform_internal_reader": {
            "available": False,
            "reason": "no verified AutoForm internal geometry measurement reader registered in first-stage agent",
        },
    }


def _command_probe(name: str) -> dict[str, Any]:
    path = shutil.which(name)
    return {"available": bool(path), "path": path or ""}


def _module_probe(name: str) -> dict[str, Any]:
    try:
        spec = importlib.util.find_spec(name)
        return {"available": bool(spec), "origin": spec.origin if spec and spec.origin else ""}
    except Exception as exc:
        return {"available": False, "error": f"{exc.__class__.__name__}: {exc}"}


def _read_stl_vertices(path: Path) -> list[tuple[float, float, float]]:
    data = path.read_bytes()
    if _looks_binary_stl(data):
        return _read_binary_stl_vertices(data)
    return _read_ascii_stl_vertices(data.decode("utf-8", errors="ignore"))


def _looks_binary_stl(data: bytes) -> bool:
    if len(data) < 84:
        return False
    triangle_count = struct.unpack("<I", data[80:84])[0]
    expected = 84 + triangle_count * 50
    return expected == len(data)


def _read_binary_stl_vertices(data: bytes) -> list[tuple[float, float, float]]:
    triangle_count = struct.unpack("<I", data[80:84])[0]
    vertices: list[tuple[float, float, float]] = []
    offset = 84
    for _ in range(triangle_count):
        record = data[offset : offset + 50]
        if len(record) < 50:
            break
        floats = struct.unpack("<12f", record[:48])
        vertices.extend(
            [
                (floats[3], floats[4], floats[5]),
                (floats[6], floats[7], floats[8]),
                (floats[9], floats[10], floats[11]),
            ]
        )
        offset += 50
    return vertices


def _read_ascii_stl_vertices(text: str) -> list[tuple[float, float, float]]:
    vertices: list[tuple[float, float, float]] = []
    for line in text.splitlines():
        parts = line.strip().split()
        if len(parts) == 4 and parts[0].casefold() == "vertex":
            vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
    return vertices


def _validate_source(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"source_geometry_path does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"source_geometry_path must be a file: {path}")
    if path.suffix.casefold() not in SUPPORTED_SUFFIXES:
        raise ValueError(f"unsupported geometry extension: {path.suffix}")


def _measurement_run_dir(output_root: str | Path, source_path: Path) -> Path:
    root = Path(output_root or CAD_MEASUREMENT_OUTPUT_ROOT)
    stem = slug(source_path.stem or "geometry")
    candidate = (root / f"{timestamp_id()}_{stem}").resolve()
    candidate.mkdir(parents=True, exist_ok=False)
    return candidate


def _filename_dimension_candidate(path: Path, *, length_unit: str) -> dict[str, Any] | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*[-xX*]\s*(\d+(?:\.\d+)?)\s*[-xX*]\s*(\d+(?:\.\d+)?)", path.stem)
    if not match:
        return None
    length, width, thickness = (float(value) for value in match.groups())
    return {
        "status": "candidate_from_filename",
        "length": _int_if_whole(length),
        "width": _int_if_whole(width),
        "thickness": _int_if_whole(thickness),
        "unit": length_unit,
        "evidence": path.name,
        "confidence": "medium",
        "note": "Parsed from filename pattern; not measured from CAD geometry.",
    }


def _int_if_whole(value: float) -> int | float:
    return int(value) if float(value).is_integer() else value


def _round_float(value: float) -> int | float:
    rounded = round(float(value), 9)
    return _int_if_whole(rounded)
