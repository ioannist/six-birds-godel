#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$repo_root" python3 - <<'PY'
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import zipfile

root = pathlib.Path(os.environ["REPO_ROOT"]).resolve()
repo_name = root.name
version_file = root / ".package-repo-snapshot-version"
config_path = root / ".package-repo-snapshot.json"

if not config_path.exists():
    raise SystemExit("Missing .package-repo-snapshot.json; configure allowed roots first.")

raw_config = json.loads(config_path.read_text(encoding="utf-8"))
if not isinstance(raw_config, dict):
    raise SystemExit("Invalid .package-repo-snapshot.json: expected a JSON object.")

excluded_dirs = set(
    raw_config.get(
        "exclude_dirs",
        [
            ".git",
            ".lake",
            ".venv",
            "venv",
            "__pycache__",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
        ],
    )
)

current_version = -1
if version_file.exists():
    raw = version_file.read_text(encoding="utf-8").strip()
    if raw.isdigit():
        current_version = int(raw)

next_version = current_version + 1
zip_path = root / f"{repo_name}_snapshot_v{next_version}.zip"

def _component_excluded(rel: pathlib.PurePosixPath) -> bool:
    return any(part in excluded_dirs for part in rel.parts[:-1])


def _snapshot_artifact(rel: pathlib.PurePosixPath) -> bool:
    name = rel.name
    return name.endswith("_snapshot.zip") or (
        name.startswith(f"{repo_name}_snapshot_v") and name.endswith(".zip")
    )


tracked_and_unignored = subprocess.check_output(
    ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
    cwd=root,
)

files: list[pathlib.Path] = []
seen: set[pathlib.PurePosixPath] = set()
for raw_path in tracked_and_unignored.decode("utf-8").split("\0"):
    if not raw_path:
        continue
    rel = pathlib.PurePosixPath(raw_path)
    if rel in seen:
        continue
    seen.add(rel)
    if _component_excluded(rel):
        continue
    if _snapshot_artifact(rel):
        continue
    path = root / rel
    if not path.exists() or not path.is_file():
        continue
    files.append(path)

if not files:
    raise SystemExit("No files to package (all files ignored).")

with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    for path in files:
        rel = path.relative_to(root).as_posix()
        zf.write(path, rel)

version_file.write_text(str(next_version), encoding="utf-8")
previous_path = None
if current_version >= 0:
    previous_path = root / f"{repo_name}_snapshot_v{current_version}.zip"
if previous_path and previous_path.exists():
    previous_path.unlink()

print(f"Wrote {zip_path}")
PY
