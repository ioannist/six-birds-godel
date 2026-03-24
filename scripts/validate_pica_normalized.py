#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent.parent


class ValidationError(Exception):
    pass


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValidationError(f"missing file: {path.relative_to(ROOT)}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValidationError(f"invalid yaml: {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValidationError(f"yaml must be mapping: {path.relative_to(ROOT)}")
    return data


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ValidationError(f"missing file: {path.relative_to(ROOT)}")
    rows: list[dict[str, Any]] = []
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"invalid jsonl at {path.relative_to(ROOT)} line {idx+1}: {exc}") from exc
        if not isinstance(obj, dict):
            raise ValidationError(f"jsonl object must be mapping at {path.relative_to(ROOT)} line {idx+1}")
        rows.append(obj)
    return rows


def main() -> int:
    try:
        ledger_map = _load_yaml(ROOT / "data" / "pica_mapping" / "ledger_surfaces.yaml")
        fig_map = _load_yaml(ROOT / "data" / "pica_mapping" / "figdata_surfaces.yaml")

        ledger_records_path = ROOT / "data" / "pica_normalized" / "ledger_records.jsonl"
        fig_records_path = ROOT / "data" / "pica_normalized" / "figdata_records.jsonl"
        source_index_path = ROOT / "data" / "pica_normalized" / "source_index.yaml"
        summary_path = ROOT / "results" / "ticket-p3" / "summary_table.csv"

        ledger_rows = _load_jsonl(ledger_records_path)
        fig_rows = _load_jsonl(fig_records_path)
        _load_yaml(source_index_path)

        if not summary_path.is_file():
            raise ValidationError(f"missing file: {summary_path.relative_to(ROOT)}")

        with summary_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            summary_rows = list(reader)
        if not summary_rows:
            raise ValidationError("summary_table.csv is empty")

        ledger_paths = set()
        for row in ledger_rows:
            sp = row.get("source_path")
            if isinstance(sp, str):
                ledger_paths.add(sp)
            else:
                raise ValidationError("ledger record missing source_path")
        fig_paths = set()
        for row in fig_rows:
            sp = row.get("source_path")
            if isinstance(sp, str):
                fig_paths.add(sp)
            else:
                raise ValidationError("figdata record missing source_path")

        mapped_ledger = ledger_map.get("surfaces", [])
        if not isinstance(mapped_ledger, list):
            raise ValidationError("ledger mapping surfaces must be list")
        for entry in mapped_ledger:
            if not isinstance(entry, dict):
                raise ValidationError("ledger mapping entry must be mapping")
            source_path = entry.get("source_path")
            if not isinstance(source_path, str):
                raise ValidationError("ledger mapping source_path missing/invalid")
            source_full = ROOT / source_path
            if source_full.exists():
                if source_path not in ledger_paths:
                    raise ValidationError(f"mapped ledger source lacks normalized records: {source_path}")

        mapped_fig = fig_map.get("entries", [])
        if not isinstance(mapped_fig, list):
            raise ValidationError("figdata mapping entries must be list")
        for entry in mapped_fig:
            if not isinstance(entry, dict):
                raise ValidationError("figdata mapping entry must be mapping")
            source_path = entry.get("file_path")
            if not isinstance(source_path, str):
                raise ValidationError("figdata mapping file_path missing/invalid")
            source_full = ROOT / source_path
            if source_full.exists():
                if source_path not in fig_paths:
                    raise ValidationError(f"mapped figdata source lacks normalized record: {source_path}")

        mapped_vendor_paths = {
            entry["source_path"]
            for entry in mapped_ledger
            if isinstance(entry, dict) and isinstance(entry.get("source_path"), str)
        } | {
            entry["file_path"]
            for entry in mapped_fig
            if isinstance(entry, dict) and isinstance(entry.get("file_path"), str)
        }

        summary_paths = {row.get("source_path") for row in summary_rows}
        for p in mapped_vendor_paths:
            if p not in summary_paths:
                raise ValidationError(f"summary_table missing mapped source path: {p}")

        # All normalized paths must resolve to an existing mapped vendor path.
        normalized_paths = ledger_paths | fig_paths
        for p in normalized_paths:
            if p not in mapped_vendor_paths:
                raise ValidationError(f"normalized source path not in mapped surfaces: {p}")
            if not (ROOT / p).exists():
                raise ValidationError(f"normalized source path does not exist in vendor tree: {p}")

    except ValidationError as exc:
        print(f"pica normalized validation failed: {exc}")
        return 1

    print("pica normalized validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
