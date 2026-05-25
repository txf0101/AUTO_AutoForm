"""Runtime bridge called by AutoForm QuickLink Export scripts."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path


def collect_quicklink_archive(archive: Path, workspace: Path) -> Path:
    """Copy one AutoForm-generated QuickLink archive into the workspace."""
    archive = archive.resolve()
    workspace = workspace.resolve()
    if not archive.exists():
        raise FileNotFoundError(archive)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_dir = workspace / "autoform_agent_data" / "quicklink" / stamp
    target_dir.mkdir(parents=True, exist_ok=True)
    target_archive = target_dir / archive.name
    shutil.copy2(archive, target_archive)

    manifest = {
        "collected_at": stamp,
        "source_archive": str(archive),
        "target_archive": str(target_archive),
        "size_bytes": target_archive.stat().st_size,
    }
    (target_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target_archive


def main(argv: list[str] | None = None) -> int:
    """CLI entry used by the generated QuickLink bridge `.cmd` file."""
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    target = collect_quicklink_archive(args.archive, args.workspace)
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
