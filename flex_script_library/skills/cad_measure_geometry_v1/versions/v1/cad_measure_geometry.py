"""Stable v1 CAD measurement script entrypoint."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def _project_root() -> Path:
    return Path(__file__).resolve().parents[5]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--params-json", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--evidence-dir", required=True)
    args = parser.parse_args()

    root = _project_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from autoform_agent.flex_scripts.cad_measurement import measure_cad_geometry

    params = json.loads(Path(args.params_json).read_text(encoding="utf-8"))
    result = measure_cad_geometry(
        params.get("source_geometry_path", ""),
        length_unit=params.get("length_unit", "mm"),
        output_root=params.get("output_root") or root / "output" / "cad_measurements",
    )
    artifact = Path(result.get("evidence_dir", "")).parent / "cad_measurement_result.json"
    result["artifacts"] = [str(artifact.resolve())] if artifact.exists() else []
    Path(args.output_json).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
