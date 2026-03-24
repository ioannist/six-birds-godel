#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent

REQUIRED_DIRS = [
    ROOT / "src" / "python" / "closure_frontier",
    ROOT / "tests" / "python",
    ROOT / "src" / "lean",
    ROOT / "data",
    ROOT / "results",
    ROOT / "docs" / "findings",
    ROOT / "docs" / "specs",
]

REQUIRED_FILES = [
    ROOT / "pyproject.toml",
    ROOT / "lakefile.lean",
    ROOT / "lean-toolchain",
    ROOT / "Makefile",
    ROOT / "src" / "python" / "closure_frontier" / "__init__.py",
    ROOT / "tests" / "python" / "test_smoke.py",
    ROOT / "src" / "lean" / "ClosureFrontier.lean",
    ROOT / "src" / "lean" / "ClosureFrontier" / "Basic.lean",
    ROOT / "docs" / "specs" / "project_manifest.yaml",
]


def main() -> int:
    missing = [str(path.relative_to(ROOT)) for path in REQUIRED_DIRS if not path.is_dir()]
    missing += [str(path.relative_to(ROOT)) for path in REQUIRED_FILES if not path.is_file()]

    if missing:
        for path in missing:
            print(f"missing: {path}")
        return 1

    print("bootstrap validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
