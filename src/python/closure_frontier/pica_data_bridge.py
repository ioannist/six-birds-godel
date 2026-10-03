from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path
from typing import Any

import yaml


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected mapping yaml: {path}")
    return data


def load_ledger_mapping() -> dict[str, Any]:
    path = repo_root() / "data" / "pica_mapping" / "ledger_surfaces.yaml"
    return _load_yaml(path)


def load_figdata_mapping() -> dict[str, Any]:
    path = repo_root() / "data" / "pica_mapping" / "figdata_surfaces.yaml"
    return _load_yaml(path)


def _parse_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    records: list[dict[str, Any]] = []
    bad = 0
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError:
            bad += 1
            records.append(
                {
                    "record_index": idx,
                    "parsed": False,
                    "top_level_keys": [],
                    "id_like": None,
                    "label_like": None,
                    "payload": None,
                }
            )
            continue
        if not isinstance(obj, dict):
            bad += 1
            records.append(
                {
                    "record_index": idx,
                    "parsed": False,
                    "top_level_keys": [],
                    "id_like": None,
                    "label_like": None,
                    "payload": None,
                }
            )
            continue
        id_like = obj.get("id") or obj.get("hypothesis_id") or obj.get("experiment_id")
        label_like = obj.get("claim") or obj.get("description") or obj.get("status")
        records.append(
            {
                "record_index": idx,
                "parsed": True,
                "top_level_keys": sorted(obj.keys()),
                "id_like": id_like if isinstance(id_like, str) else None,
                "label_like": label_like if isinstance(label_like, str) else None,
                "payload": obj,
            }
        )
    return records, bad


def _parse_csv(path: Path) -> tuple[list[str], int]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, [])
        rows = sum(1 for _ in reader)
    return [str(h) for h in header], rows


def _parse_csv_gz(path: Path) -> tuple[list[str], int]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, [])
        rows = sum(1 for _ in reader)
    return [str(h) for h in header], rows


def _parse_json(path: Path) -> tuple[list[str], int]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(obj, dict):
        return sorted(obj.keys()), 1
    if isinstance(obj, list):
        return [], len(obj)
    return [], 1


def normalize_ledger_records() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    mapping = load_ledger_mapping()
    surfaces = mapping.get("surfaces", [])
    if not isinstance(surfaces, list):
        raise ValueError("ledger_surfaces.surfaces must be a list")

    records: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    for surface in surfaces:
        if not isinstance(surface, dict):
            raise ValueError("ledger surface entry must be mapping")
        source_path = str(surface["source_path"])
        logical_name = str(surface["logical_name"])
        full_path = repo_root() / source_path
        if not full_path.is_file():
            source_rows.append(
                {
                    "source_path": source_path,
                    "source_family": "ledger",
                    "coarse_type": logical_name,
                    "parsed_status": "missing",
                    "record_count": 0,
                    "key_summary": "",
                }
            )
            continue

        parsed, bad = _parse_jsonl(full_path)
        key_union: set[str] = set()
        for entry in parsed:
            for k in entry["top_level_keys"]:
                key_union.add(k)
            records.append(
                {
                    "source_path": source_path,
                    "source_family": "ledger",
                    "surface_kind": logical_name,
                    "record_index": entry["record_index"],
                    "parsed": entry["parsed"],
                    "top_level_keys": entry["top_level_keys"],
                    "id_like": entry["id_like"],
                    "label_like": entry["label_like"],
                    "payload": entry["payload"],
                }
            )

        status = "ok" if bad == 0 else "partial"
        source_rows.append(
            {
                "source_path": source_path,
                "source_family": "ledger",
                "coarse_type": logical_name,
                "parsed_status": status,
                "record_count": len(parsed),
                "key_summary": ",".join(sorted(key_union)),
            }
        )

    return records, source_rows


def normalize_figdata_records() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    mapping = load_figdata_mapping()
    entries = mapping.get("entries", [])
    if not isinstance(entries, list):
        raise ValueError("figdata_surfaces.entries must be a list")

    records: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("figdata entry must be mapping")
        source_path = str(entry["file_path"])
        fmt = str(entry["format"])
        coarse = str(entry["coarse_category"])
        relevance = str(entry["relevance"])
        full_path = repo_root() / source_path

        parsed = False
        headers: list[str] = []
        row_count = 0
        parse_note = "unknown"

        if full_path.is_file():
            try:
                if fmt == "json":
                    headers, row_count = _parse_json(full_path)
                    parsed = True
                    parse_note = "parsed_json"
                elif fmt == "csv":
                    headers, row_count = _parse_csv(full_path)
                    parsed = True
                    parse_note = "parsed_csv"
                elif fmt == "csv.gz":
                    headers, row_count = _parse_csv_gz(full_path)
                    parsed = True
                    parse_note = "parsed_csv_gz"
                else:
                    parse_note = "inventory_only"
            except Exception as exc:
                parse_note = f"parse_error:{type(exc).__name__}"
                parsed = False
        else:
            parse_note = "missing"

        records.append(
            {
                "source_path": source_path,
                "source_family": "figdata",
                "surface_kind": coarse,
                "format": fmt,
                "relevance": relevance,
                "parsed": parsed,
                "row_count": row_count,
                "headers": headers,
                "parse_note": parse_note,
            }
        )
        source_rows.append(
            {
                "source_path": source_path,
                "source_family": "figdata",
                "coarse_type": coarse,
                "parsed_status": "ok" if parsed else ("missing" if parse_note == "missing" else "partial"),
                "record_count": row_count,
                "key_summary": ",".join(headers),
            }
        )

    return records, source_rows
