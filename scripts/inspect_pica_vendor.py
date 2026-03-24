#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "python"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from closure_frontier.pica_adapter import (  # noqa: E402
    inventory_key_surfaces,
    list_figdata_files,
    list_ledger_files,
    load_primitives_yaml,
    probe_rust_workspace,
    vendor_root,
)


def main() -> int:
    out_dir = ROOT / "results" / "ticket-p1"
    out_dir.mkdir(parents=True, exist_ok=True)

    inventory = inventory_key_surfaces()
    primitives = load_primitives_yaml()
    ledger_files = list_ledger_files()
    figdata_files = list_figdata_files()
    rust_probe = probe_rust_workspace(timeout_seconds=5.0)

    inventory["primitives_yaml_top_keys"] = sorted(primitives.keys())
    inventory["ledger_files"] = ledger_files
    inventory["figdata_files"] = figdata_files

    smoke = {
        "vendor_root": str(vendor_root()),
        "vendor_root_found": True,
        "primitives_loaded": True,
        "ledger_files_found": len(ledger_files),
        "figdata_files_found": len(figdata_files),
        "rust_probe": rust_probe,
    }

    inv_path = out_dir / "vendor_inventory.json"
    smoke_path = out_dir / "smoke_summary.json"
    inv_path.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    smoke_path.write_text(json.dumps(smoke, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {inv_path}")
    print(f"wrote {smoke_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
