#!/usr/bin/env python3
from __future__ import annotations

import csv
from pathlib import Path
import sys
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "data" / "schemas" / "pica_atlas_schema.yaml"


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


def main() -> int:
    try:
        schema = _load_yaml(SCHEMA_PATH)
        req_files = schema.get("required_files")
        if not isinstance(req_files, list) or not req_files:
            raise ValidationError("schema.required_files must be non-empty list")
        vocab = schema.get("allowed_vocabularies")
        if not isinstance(vocab, dict):
            raise ValidationError("schema.allowed_vocabularies must be mapping")

        allowed_prov = set(vocab.get("provenance_type", []))
        allowed_ev = set(vocab.get("evidence_status", []))
        allowed_pk = set(vocab.get("program_kind", []))
        allowed_cs = set(vocab.get("crosswalk_status", []))
        if not (allowed_prov and allowed_ev and allowed_pk and allowed_cs):
            raise ValidationError("schema vocabularies missing")

        for rel in req_files:
            if not isinstance(rel, str):
                raise ValidationError("required_files entries must be strings")
            if not (ROOT / rel).is_file():
                raise ValidationError(f"missing required atlas file: {rel}")

        cell_doc = _load_yaml(ROOT / "data" / "pica_atlas" / "cell_atlas.yaml")
        prog_doc = _load_yaml(ROOT / "data" / "pica_atlas" / "program_atlas.yaml")
        xwalk_doc = _load_yaml(ROOT / "data" / "pica_atlas" / "concept_crosswalk.yaml")

        cell_entries = cell_doc.get("entries")
        prog_entries = prog_doc.get("entries")
        xwalk_entries = xwalk_doc.get("entries")
        if not isinstance(cell_entries, list) or not cell_entries:
            raise ValidationError("cell_atlas entries missing/empty")
        if not isinstance(prog_entries, list) or not prog_entries:
            raise ValidationError("program_atlas entries missing/empty")
        if not isinstance(xwalk_entries, list) or not xwalk_entries:
            raise ValidationError("concept_crosswalk entries missing/empty")

        seen_cell: set[str] = set()
        for idx, entry in enumerate(cell_entries):
            if not isinstance(entry, dict):
                raise ValidationError(f"cell entry[{idx}] must be mapping")
            for field in ("id", "label", "source_paths", "provenance_type", "evidence_status"):
                if field not in entry:
                    raise ValidationError(f"cell entry[{idx}] missing field: {field}")
            cid = entry["id"]
            if cid in seen_cell:
                raise ValidationError(f"duplicate cell id: {cid}")
            seen_cell.add(cid)
            if entry["provenance_type"] not in allowed_prov:
                raise ValidationError(f"cell {cid} invalid provenance_type: {entry['provenance_type']}")
            if entry["evidence_status"] not in allowed_ev:
                raise ValidationError(f"cell {cid} invalid evidence_status: {entry['evidence_status']}")
            paths = entry["source_paths"]
            if not isinstance(paths, list) or not paths:
                raise ValidationError(f"cell {cid} source_paths must be non-empty list")
            for sp in paths:
                if not isinstance(sp, str) or not (ROOT / sp).exists():
                    raise ValidationError(f"cell {cid} missing source path: {sp}")

        seen_prog: set[str] = set()
        for idx, entry in enumerate(prog_entries):
            if not isinstance(entry, dict):
                raise ValidationError(f"program entry[{idx}] must be mapping")
            for field in ("id", "label", "program_kind", "member_cells", "source_paths", "provenance_type", "evidence_status"):
                if field not in entry:
                    raise ValidationError(f"program entry[{idx}] missing field: {field}")
            pid = entry["id"]
            if pid in seen_prog:
                raise ValidationError(f"duplicate program id: {pid}")
            seen_prog.add(pid)
            if entry["program_kind"] not in allowed_pk:
                raise ValidationError(f"program {pid} invalid program_kind: {entry['program_kind']}")
            if entry["provenance_type"] not in allowed_prov:
                raise ValidationError(f"program {pid} invalid provenance_type: {entry['provenance_type']}")
            if entry["evidence_status"] not in allowed_ev:
                raise ValidationError(f"program {pid} invalid evidence_status: {entry['evidence_status']}")
            member_cells = entry["member_cells"]
            if not isinstance(member_cells, list):
                raise ValidationError(f"program {pid} member_cells must be list")
            for cid in member_cells:
                if cid not in seen_cell:
                    raise ValidationError(f"program {pid} references unknown cell id: {cid}")
            paths = entry["source_paths"]
            if not isinstance(paths, list) or not paths:
                raise ValidationError(f"program {pid} source_paths must be non-empty list")
            for sp in paths:
                if not isinstance(sp, str) or not (ROOT / sp).exists():
                    raise ValidationError(f"program {pid} missing source path: {sp}")

        atlas_ids = seen_cell | seen_prog
        for idx, entry in enumerate(xwalk_entries):
            if not isinstance(entry, dict):
                raise ValidationError(f"crosswalk entry[{idx}] must be mapping")
            for field in ("our_concept", "nearest_pica_target", "status", "supporting_atlas_ids"):
                if field not in entry:
                    raise ValidationError(f"crosswalk entry[{idx}] missing field: {field}")
            status = entry["status"]
            if status not in allowed_cs:
                raise ValidationError(f"crosswalk entry[{idx}] invalid status: {status}")
            target = entry["nearest_pica_target"]
            if status == "none":
                continue
            if not isinstance(target, str):
                raise ValidationError(f"crosswalk entry[{idx}] nearest_pica_target must be string")
            support = entry["supporting_atlas_ids"]
            if not isinstance(support, list):
                raise ValidationError(f"crosswalk entry[{idx}] supporting_atlas_ids must be list")
            for sid in support:
                if sid not in atlas_ids:
                    raise ValidationError(f"crosswalk entry[{idx}] unknown supporting atlas id: {sid}")

        summary = ROOT / "results" / "ticket-p4" / "atlas_summary.csv"
        if not summary.is_file():
            raise ValidationError("missing file: results/ticket-p4/atlas_summary.csv")
        with summary.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        if not rows:
            raise ValidationError("atlas_summary.csv is empty")

    except ValidationError as exc:
        print(f"pica atlas validation failed: {exc}")
        return 1

    print("pica atlas validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
