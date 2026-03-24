#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "python"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from closure_frontier.pica_data_bridge import (  # noqa: E402
    load_figdata_mapping,
    load_ledger_mapping,
    normalize_figdata_records,
    normalize_ledger_records,
)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> int:
    normalized_dir = ROOT / "data" / "pica_normalized"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    results_dir = ROOT / "results" / "ticket-p3"
    results_dir.mkdir(parents=True, exist_ok=True)

    ledger_records, ledger_sources = normalize_ledger_records()
    fig_records, fig_sources = normalize_figdata_records()
    summary_rows = ledger_sources + fig_sources

    ledger_out = normalized_dir / "ledger_records.jsonl"
    fig_out = normalized_dir / "figdata_records.jsonl"
    source_index_out = normalized_dir / "source_index.yaml"
    summary_out = results_dir / "summary_table.csv"

    _write_jsonl(ledger_out, ledger_records)
    _write_jsonl(fig_out, fig_records)

    source_index = {
        "mapping_sources": {
            "ledger_surfaces": "data/pica_mapping/ledger_surfaces.yaml",
            "figdata_surfaces": "data/pica_mapping/figdata_surfaces.yaml",
        },
        "counts": {
            "ledger_records": len(ledger_records),
            "figdata_records": len(fig_records),
            "source_rows": len(summary_rows),
        },
        "surfaces": {
            "ledger": load_ledger_mapping().get("surfaces", []),
            "figdata": load_figdata_mapping().get("entries", []),
        },
    }
    source_index_out.write_text(yaml.safe_dump(source_index, sort_keys=False), encoding="utf-8")

    with summary_out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source_path",
                "source_family",
                "coarse_type",
                "parsed_status",
                "record_count",
                "key_summary",
            ],
        )
        writer.writeheader()
        for row in summary_rows:
            writer.writerow(row)

    print(f"wrote {ledger_out}")
    print(f"wrote {fig_out}")
    print(f"wrote {source_index_out}")
    print(f"wrote {summary_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
