from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any

import yaml


VENDOR_REL = Path("vendors") / "six-birds-pica"
THEORY_PRIMITIVES_REL = Path("theory") / "primitives.yaml"
LEDGER_REL = Path("lab") / "ledger"
FIGDATA_REL = Path("paper") / "figdata"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def vendor_root() -> Path:
    root = repo_root() / VENDOR_REL
    if not root.is_dir():
        raise FileNotFoundError(f"missing vendor root: {root}")
    return root


def primitives_yaml_path() -> Path:
    path = vendor_root() / THEORY_PRIMITIVES_REL
    if not path.is_file():
        raise FileNotFoundError(f"missing primitives yaml: {path}")
    return path


def ledger_dir() -> Path:
    path = vendor_root() / LEDGER_REL
    if not path.is_dir():
        raise FileNotFoundError(f"missing ledger dir: {path}")
    return path


def figdata_dir() -> Path:
    path = vendor_root() / FIGDATA_REL
    if not path.is_dir():
        raise FileNotFoundError(f"missing figdata dir: {path}")
    return path


def load_primitives_yaml() -> dict[str, Any]:
    path = primitives_yaml_path()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"primitives yaml must parse to a mapping: {path}")
    return data


def list_ledger_files() -> list[str]:
    root = ledger_dir()
    files = [p for p in root.iterdir() if p.is_file()]
    return sorted(str(p.relative_to(vendor_root())) for p in files)


def list_figdata_files() -> list[str]:
    root = figdata_dir()
    files = [p for p in root.iterdir() if p.is_file()]
    return sorted(str(p.relative_to(vendor_root())) for p in files)


def inventory_key_surfaces() -> dict[str, Any]:
    vroot = vendor_root()
    required = {
        "analysis": vroot / "analysis",
        "crates": vroot / "crates",
        "lab_ledger": vroot / LEDGER_REL,
        "paper_figdata": vroot / FIGDATA_REL,
        "theory_primitives_yaml": vroot / THEORY_PRIMITIVES_REL,
    }
    missing = [name for name, path in required.items() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing required vendor surfaces: {missing}")

    return {
        "vendor_root": str(vroot),
        "required_surfaces": {
            "analysis": {"path": "analysis", "exists": required["analysis"].is_dir()},
            "crates": {"path": "crates", "exists": required["crates"].is_dir()},
            "lab_ledger": {
                "path": str(LEDGER_REL.as_posix()),
                "exists": required["lab_ledger"].is_dir(),
                "file_count": len(list_ledger_files()),
            },
            "paper_figdata": {
                "path": str(FIGDATA_REL.as_posix()),
                "exists": required["paper_figdata"].is_dir(),
                "file_count": len(list_figdata_files()),
            },
            "theory_primitives_yaml": {
                "path": str(THEORY_PRIMITIVES_REL.as_posix()),
                "exists": required["theory_primitives_yaml"].is_file(),
            },
        },
    }


def probe_rust_workspace(timeout_seconds: float = 5.0) -> dict[str, Any]:
    vroot = vendor_root()
    cargo_toml = vroot / "Cargo.toml"
    if not cargo_toml.is_file():
        return {
            "workspace_detected": False,
            "cargo_metadata_attempted": False,
            "cargo_metadata_ok": False,
            "detail": "Cargo.toml missing",
        }
    try:
        proc = subprocess.run(
            ["cargo", "metadata", "--no-deps", "--format-version", "1"],
            cwd=vroot,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError:
        return {
            "workspace_detected": True,
            "cargo_metadata_attempted": False,
            "cargo_metadata_ok": False,
            "detail": "cargo not found",
        }
    except subprocess.TimeoutExpired:
        return {
            "workspace_detected": True,
            "cargo_metadata_attempted": True,
            "cargo_metadata_ok": False,
            "detail": f"cargo metadata timed out after {timeout_seconds}s",
        }

    return {
        "workspace_detected": True,
        "cargo_metadata_attempted": True,
        "cargo_metadata_ok": proc.returncode == 0,
        "detail": "ok" if proc.returncode == 0 else (proc.stderr.strip() or "cargo metadata failed"),
    }
