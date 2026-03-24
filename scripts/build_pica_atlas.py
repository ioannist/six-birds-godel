#!/usr/bin/env python3
from __future__ import annotations

import csv
import gzip
from pathlib import Path
import re
import sys
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent.parent

LOO_CELL_MAP = ROOT / "vendors" / "six-birds-pica" / "paper" / "figdata" / "loo_cell_map.csv"
T4_TAXONOMY = ROOT / "vendors" / "six-birds-pica" / "paper" / "figdata" / "T4_taxonomy_generators.csv"
RUN_SUMMARY = ROOT / "vendors" / "six-birds-pica" / "paper" / "figdata" / "run_summary_table.csv.gz"
PRIMITIVES_YAML = ROOT / "vendors" / "six-birds-pica" / "theory" / "primitives.yaml"


def _norm_id(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _parse_cell_label(label: str) -> tuple[str | None, str | None]:
    normalized = label.replace("←", "<-").replace(" ", "")
    m = re.match(r"^P(\d+)<-P(\d+)$", normalized)
    if not m:
        return None, None
    return f"P{m.group(1)}", f"P{m.group(2)}"


def _split_cells(raw: str) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(";") if part.strip()]


def main() -> int:
    atlas_dir = ROOT / "data" / "pica_atlas"
    atlas_dir.mkdir(parents=True, exist_ok=True)
    results_dir = ROOT / "results" / "ticket-p4"
    results_dir.mkdir(parents=True, exist_ok=True)

    # Build cell atlas from explicit cell maps and taxonomy configuration cells.
    cells: dict[str, dict[str, Any]] = {}

    with LOO_CELL_MAP.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            label = (row.get("cell_label") or "").replace(" ", "")
            if not label:
                continue
            actor, informant = _parse_cell_label(label)
            cid = f"cell_{_norm_id(label)}"
            entry = cells.get(cid)
            if entry is None:
                entry = {
                    "id": cid,
                    "label": label.replace("<-", "←"),
                    "primitive_pair": {"actor": actor, "informant": informant},
                    "source_paths": [str(LOO_CELL_MAP.relative_to(ROOT))],
                    "provenance_type": "figdata",
                    "evidence_status": "observed",
                }
                cells[cid] = entry
            else:
                if str(LOO_CELL_MAP.relative_to(ROOT)) not in entry["source_paths"]:
                    entry["source_paths"].append(str(LOO_CELL_MAP.relative_to(ROOT)))

    with T4_TAXONOMY.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            for raw_label in _split_cells(row.get("enabled_cells_P", "") or ""):
                label = raw_label.replace(" ", "")
                actor, informant = _parse_cell_label(label)
                if actor is None:
                    continue
                cid = f"cell_{_norm_id(label)}"
                entry = cells.get(cid)
                if entry is None:
                    cells[cid] = {
                        "id": cid,
                        "label": label.replace("<-", "←"),
                        "primitive_pair": {"actor": actor, "informant": informant},
                        "source_paths": [str(T4_TAXONOMY.relative_to(ROOT))],
                        "provenance_type": "figdata",
                        "evidence_status": "observed",
                    }
                else:
                    if str(T4_TAXONOMY.relative_to(ROOT)) not in entry["source_paths"]:
                        entry["source_paths"].append(str(T4_TAXONOMY.relative_to(ROOT)))

    cell_atlas = {
        "atlas_id": "pica_cell_atlas",
        "version": "0.1.0",
        "entries": sorted(cells.values(), key=lambda e: e["id"]),
    }
    cell_path = atlas_dir / "cell_atlas.yaml"
    cell_path.write_text(yaml.safe_dump(cell_atlas, sort_keys=False), encoding="utf-8")

    # Build program atlas from taxonomy + explicit LOO ablations + run summary config evidence.
    programs: dict[str, dict[str, Any]] = {}

    with T4_TAXONOMY.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            config = (row.get("config_name") or "").strip()
            if not config:
                continue
            family = (row.get("family") or "").strip().lower()
            if config in {"empty", "baseline", "full_action"}:
                kind = "baseline_style"
            elif "row" in family or "group" in family or "_" in config:
                kind = "row_group"
            else:
                kind = "configuration"
            member_cells = []
            for raw_label in _split_cells(row.get("enabled_cells_P", "") or ""):
                cid = f"cell_{_norm_id(raw_label.replace(' ', ''))}"
                if cid in cells:
                    member_cells.append(cid)
            pid = f"prog_{_norm_id(config)}"
            programs[pid] = {
                "id": pid,
                "label": config,
                "program_kind": kind,
                "member_cells": sorted(set(member_cells)),
                "source_paths": [str(T4_TAXONOMY.relative_to(ROOT))],
                "provenance_type": "figdata",
                "evidence_status": "observed",
            }

    with LOO_CELL_MAP.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            cfg = (row.get("config_name") or "").strip()
            cell_label = (row.get("cell_label") or "").replace(" ", "")
            if not cfg or not cell_label:
                continue
            cid = f"cell_{_norm_id(cell_label)}"
            pid = f"prog_{_norm_id(cfg)}"
            programs[pid] = {
                "id": pid,
                "label": cfg,
                "program_kind": "key_ablation",
                "member_cells": [cid] if cid in cells else [],
                "source_paths": [str(LOO_CELL_MAP.relative_to(ROOT))],
                "provenance_type": "figdata",
                "evidence_status": "observed",
            }

    # Ensure baseline/full_action style evidence appears from run summary config names if available.
    run_configs: set[str] = set()
    with gzip.open(RUN_SUMMARY, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            cfg = (row.get("config_name") or "").strip()
            if cfg:
                run_configs.add(cfg)
    for cfg in sorted({"baseline", "full_action", "empty"} & run_configs):
        pid = f"prog_{_norm_id(cfg)}"
        if pid not in programs:
            programs[pid] = {
                "id": pid,
                "label": cfg,
                "program_kind": "baseline_style",
                "member_cells": [],
                "source_paths": [str(RUN_SUMMARY.relative_to(ROOT))],
                "provenance_type": "figdata",
                "evidence_status": "partial",
            }
        else:
            sp = str(RUN_SUMMARY.relative_to(ROOT))
            if sp not in programs[pid]["source_paths"]:
                programs[pid]["source_paths"].append(sp)

    program_atlas = {
        "atlas_id": "pica_program_atlas",
        "version": "0.1.0",
        "entries": sorted(programs.values(), key=lambda e: e["id"]),
    }
    program_path = atlas_dir / "program_atlas.yaml"
    program_path.write_text(yaml.safe_dump(program_atlas, sort_keys=False), encoding="utf-8")

    primitives = yaml.safe_load(PRIMITIVES_YAML.read_text(encoding="utf-8"))
    primitive_ids: list[str] = []
    if isinstance(primitives, dict):
        plist = primitives.get("primitives", [])
        if isinstance(plist, list):
            for item in plist:
                if isinstance(item, dict) and isinstance(item.get("id"), str):
                    primitive_ids.append(item["id"])

    crosswalk = {
        "atlas_id": "pica_concept_crosswalk",
        "version": "0.1.0",
        "entries": [
            {
                "our_concept": "packaging",
                "nearest_pica_target": "cell_p1_p5",
                "status": "partial",
                "supporting_atlas_ids": ["cell_p1_p5", "prog_baseline", "prog_full_action"],
            },
            {
                "our_concept": "accounting",
                "nearest_pica_target": "cell_p2_p6",
                "status": "direct",
                "supporting_atlas_ids": ["cell_p2_p6"],
            },
            {
                "our_concept": "protocol",
                "nearest_pica_target": "cell_p3_p4",
                "status": "partial",
                "supporting_atlas_ids": ["cell_p3_p4"],
            },
            {
                "our_concept": "gating",
                "nearest_pica_target": "cell_p2_p5",
                "status": "direct",
                "supporting_atlas_ids": ["cell_p2_p5"],
            },
            {
                "our_concept": "rewrite",
                "nearest_pica_target": "cell_p1_p5",
                "status": "partial",
                "supporting_atlas_ids": ["cell_p1_p5"],
            },
            {
                "our_concept": "lens_sector",
                "nearest_pica_target": "cell_p3_p4",
                "status": "partial",
                "supporting_atlas_ids": ["cell_p3_p4"],
            },
        ],
        "primitive_ids_seen": sorted(set(primitive_ids)),
    }
    crosswalk_path = atlas_dir / "concept_crosswalk.yaml"
    crosswalk_path.write_text(yaml.safe_dump(crosswalk, sort_keys=False), encoding="utf-8")

    summary_path = ROOT / "results" / "ticket-p4" / "atlas_summary.csv"
    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "atlas_family",
                "id",
                "label_or_concept",
                "kind_or_status",
                "provenance_type",
                "evidence_status",
                "source_paths",
                "member_count",
            ],
        )
        writer.writeheader()
        for entry in cell_atlas["entries"]:
            writer.writerow(
                {
                    "atlas_family": "cell",
                    "id": entry["id"],
                    "label_or_concept": entry["label"],
                    "kind_or_status": "cell",
                    "provenance_type": entry["provenance_type"],
                    "evidence_status": entry["evidence_status"],
                    "source_paths": ";".join(entry["source_paths"]),
                    "member_count": "",
                }
            )
        for entry in program_atlas["entries"]:
            writer.writerow(
                {
                    "atlas_family": "program",
                    "id": entry["id"],
                    "label_or_concept": entry["label"],
                    "kind_or_status": entry["program_kind"],
                    "provenance_type": entry["provenance_type"],
                    "evidence_status": entry["evidence_status"],
                    "source_paths": ";".join(entry["source_paths"]),
                    "member_count": len(entry["member_cells"]),
                }
            )
        for entry in crosswalk["entries"]:
            writer.writerow(
                {
                    "atlas_family": "crosswalk",
                    "id": "",
                    "label_or_concept": entry["our_concept"],
                    "kind_or_status": entry["status"],
                    "provenance_type": "",
                    "evidence_status": "",
                    "source_paths": ";".join(entry["supporting_atlas_ids"]),
                    "member_count": "",
                }
            )

    print(f"wrote {cell_path}")
    print(f"wrote {program_path}")
    print(f"wrote {crosswalk_path}")
    print(f"wrote {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
