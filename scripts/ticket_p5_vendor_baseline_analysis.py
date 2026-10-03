#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path
import re
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent.parent

PROGRAM_ATLAS = ROOT / "data" / "pica_atlas" / "program_atlas.yaml"
CELL_ATLAS = ROOT / "data" / "pica_atlas" / "cell_atlas.yaml"
LEDGER_RECORDS = ROOT / "data" / "pica_normalized" / "ledger_records.jsonl"
FIGDATA_RECORDS = ROOT / "data" / "pica_normalized" / "figdata_records.jsonl"

TOY_REPORT_PATHS = [
    ROOT / "results" / "ticket-05" / "report.md",
    ROOT / "results" / "ticket-06" / "report.md",
    ROOT / "results" / "ticket-06-1" / "report.md",
    ROOT / "results" / "ticket-06-2" / "report.md",
    ROOT / "results" / "ticket-06-3" / "report.md",
    ROOT / "results" / "ticket-06-4" / "report.md",
]


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected mapping yaml: {path}")
    return data


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            item = json.loads(raw)
            if isinstance(item, dict):
                rows.append(item)
    return rows


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def lower_payload_text(record: dict[str, Any]) -> str:
    payload = record.get("payload")
    if isinstance(payload, dict):
        return json.dumps(payload, ensure_ascii=False).lower()
    return ""


def parse_program_profiles(
    programs: list[dict[str, Any]], ledger_records: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    ledger_texts = [lower_payload_text(r) for r in ledger_records]
    rows: list[dict[str, Any]] = []

    for entry in programs:
        program_id = str(entry.get("id", ""))
        label = str(entry.get("label", ""))
        kind = str(entry.get("program_kind", ""))
        source_paths = [str(p) for p in entry.get("source_paths", []) if isinstance(p, str)]
        label_l = label.lower()

        has_run_summary = any("run_summary_table.csv.gz" in p for p in source_paths)
        has_loo = any("loo_cell_map.csv" in p for p in source_paths)
        has_taxonomy = any("T4_taxonomy_generators.csv" in p for p in source_paths)
        ledger_mentions = 0
        if label_l:
            for text in ledger_texts:
                if label_l in text:
                    ledger_mentions += 1

        support_score = (
            (2.0 if has_run_summary else 0.0)
            + (2.0 if has_loo else 0.0)
            + (1.0 if has_taxonomy else 0.0)
            + min(3, ledger_mentions) * 0.5
        )
        if support_score >= 4.0:
            support_class = "strong_surface_support"
        elif support_score >= 2.0:
            support_class = "moderate_surface_support"
        else:
            support_class = "limited_surface_support"

        rows.append(
            {
                "program_id": program_id,
                "label": label,
                "program_kind": kind,
                "evidence_status": str(entry.get("evidence_status", "")),
                "member_cell_count": int(len(entry.get("member_cells", []))),
                "has_run_summary_source": int(has_run_summary),
                "has_loo_source": int(has_loo),
                "has_taxonomy_source": int(has_taxonomy),
                "ledger_mentions": ledger_mentions,
                "support_score": round(support_score, 3),
                "support_class": support_class,
            }
        )

    rows.sort(
        key=lambda r: (
            -float(r["support_score"]),
            str(r["program_kind"]),
            str(r["label"]),
            str(r["program_id"]),
        )
    )
    return rows


def parse_ablation_summary(cells: list[dict[str, Any]], programs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    full_action_cells: set[str] = set()
    full_all_cells: set[str] = set()
    baseline_cells: set[str] = set()

    for program in programs:
        label = str(program.get("label", ""))
        member_cells = {str(c) for c in program.get("member_cells", []) if isinstance(c, str)}
        if label == "baseline":
            baseline_cells |= member_cells
        if label == "full_action":
            full_action_cells |= member_cells
        if label == "full_all":
            full_all_cells |= member_cells

    rows: list[dict[str, Any]] = []
    for cell in cells:
        cid = str(cell.get("id", ""))
        loo_configs = []
        row_group_configs = []
        for program in programs:
            member_cells = {str(c) for c in program.get("member_cells", []) if isinstance(c, str)}
            if cid not in member_cells:
                continue
            label = str(program.get("label", ""))
            if label.startswith("loo_"):
                loo_configs.append(label)
            if str(program.get("program_kind", "")) == "row_group":
                row_group_configs.append(label)

        # Conservative impact proxy: explicit ablation coverage + configuration reach.
        impact_proxy = len(loo_configs) * 3.0 + len(row_group_configs) * 0.15
        if cid in baseline_cells:
            impact_proxy += 0.25
        if cid in full_action_cells:
            impact_proxy += 0.25
        if cid in full_all_cells:
            impact_proxy += 0.25

        rows.append(
            {
                "cell_id": cid,
                "label": str(cell.get("label", "")),
                "actor": str(cell.get("primitive_pair", {}).get("actor", "")),
                "informant": str(cell.get("primitive_pair", {}).get("informant", "")),
                "loo_program_count": len(loo_configs),
                "row_group_program_count": len(row_group_configs),
                "in_baseline": int(cid in baseline_cells),
                "in_full_action": int(cid in full_action_cells),
                "in_full_all": int(cid in full_all_cells),
                "impact_proxy_score": round(impact_proxy, 3),
            }
        )

    rows.sort(
        key=lambda r: (
            -float(r["impact_proxy_score"]),
            -int(r["loo_program_count"]),
            -int(r["row_group_program_count"]),
            str(r["cell_id"]),
        )
    )
    return rows


def assess_toy_takeaways(
    program_profiles: list[dict[str, Any]],
    ablation_summary: list[dict[str, Any]],
    figdata_records: list[dict[str, Any]],
    toy_reports_present: list[str],
) -> dict[str, list[dict[str, Any]]]:
    labels = {str(r["label"]): r for r in program_profiles}
    robust_headers = []
    for row in figdata_records:
        if str(row.get("surface_kind")) == "robustness":
            robust_headers = [str(h) for h in row.get("headers", []) if isinstance(h, str)]
            break

    supported: list[dict[str, Any]] = []
    unsupported: list[dict[str, Any]] = []
    not_assessable: list[dict[str, Any]] = []

    baseline = labels.get("baseline")
    full_action = labels.get("full_action")
    full_all = labels.get("full_all")
    if baseline and full_action and full_all:
        not_assessable.append(
            {
                "id": "toy_baseline_weaker_than_richer_configs",
                "note": "Baseline/full_action/full_all surfaces are present. Presence alone does not establish superiority; use quantitative program deltas.",
                "evidence_paths": [
                    "data/pica_atlas/program_atlas.yaml",
                    "data/pica_normalized/figdata_records.jsonl",
                ],
            }
        )
    else:
        not_assessable.append(
            {
                "id": "toy_baseline_weaker_than_richer_configs",
                "note": "Could not confirm baseline/full_action/full_all together from current normalized/atlas inputs.",
                "evidence_paths": ["data/pica_atlas/program_atlas.yaml"],
            }
        )

    if ablation_summary and max(float(r["impact_proxy_score"]) for r in ablation_summary) > min(
        float(r["impact_proxy_score"]) for r in ablation_summary
    ):
        not_assessable.append(
            {
                "id": "toy_heterogeneous_cell_importance",
                "note": "LOO and row/group coverage varies. Coverage counts are not cell effects; use the quantitative cell delta table.",
                "evidence_paths": [
                    "data/pica_atlas/program_atlas.yaml",
                    "results/ticket-p5/ablation_summary.csv",
                ],
            }
        )
    else:
        not_assessable.append(
            {
                "id": "toy_heterogeneous_cell_importance",
                "note": "LOO/cell coverage does not show measurable heterogeneity in the shipped subset.",
                "evidence_paths": ["data/pica_atlas/program_atlas.yaml"],
            }
        )

    if robust_headers:
        not_assessable.append(
            {
                "id": "toy_interaction_structure_needed",
                "note": "A robustness surface is present. Its presence proves neither interaction gain nor the inadequacy of a scalar proxy.",
                "evidence_paths": ["data/pica_normalized/figdata_records.jsonl"],
            }
        )
    else:
        not_assessable.append(
            {
                "id": "toy_interaction_structure_needed",
                "note": "No shipped robustness surface was parsed in normalized records.",
                "evidence_paths": ["data/pica_normalized/figdata_records.jsonl"],
            }
        )

    if toy_reports_present:
        not_assessable.append(
            {
                "id": "toy_broad_uniqueness_stability_claims",
                "note": "Toy falsification exists, but direct vendor-side uniqueness/stability equivalence is not directly testable from shipped normalized subset.",
                "evidence_paths": toy_reports_present,
            }
        )
    else:
        unsupported.append(
            {
                "id": "toy_broad_uniqueness_stability_claims",
                "note": "No toy reports available to compare against vendor surfaces.",
                "evidence_paths": [],
            }
        )

    return {
        "supported_by_vendor": supported,
        "unsupported_by_vendor": unsupported,
        "not_assessable_from_shipped_data": not_assessable,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    output_dir = ROOT / "results" / "ticket-p5"
    output_dir.mkdir(parents=True, exist_ok=True)

    program_atlas = load_yaml(PROGRAM_ATLAS)
    cell_atlas = load_yaml(CELL_ATLAS)
    ledger_records = load_jsonl(LEDGER_RECORDS)
    figdata_records = load_jsonl(FIGDATA_RECORDS)

    program_entries = [e for e in program_atlas.get("entries", []) if isinstance(e, dict)]
    cell_entries = [e for e in cell_atlas.get("entries", []) if isinstance(e, dict)]

    major_programs: list[dict[str, Any]] = []
    for entry in program_entries:
        label = str(entry.get("label", ""))
        kind = str(entry.get("program_kind", ""))
        if label in {"baseline", "full_action", "full_all"}:
            major_programs.append(entry)
            continue
        if label.startswith("loo_"):
            major_programs.append(entry)
            continue
        if kind == "row_group":
            major_programs.append(entry)

    profiles = parse_program_profiles(major_programs, ledger_records)
    ablations = parse_ablation_summary(cell_entries, major_programs)

    toy_reports_present = [str(path.relative_to(ROOT)) for path in TOY_REPORT_PATHS if path.exists()]
    survivor_failure = {
        "version": "0.1.0",
        "analysis_id": "ticket_p5_vendor_baseline",
        "programs": assess_toy_takeaways(profiles, ablations, figdata_records, toy_reports_present),
        "notes": {
            "guardrail": "Conservative support/provenance audit only; no effect-size claim promotion.",
            "toy_report_inputs": toy_reports_present,
            "ranking_method": "Cell ranking uses explicit LOO+row-group coverage proxy, not claimed causal effect size.",
        },
    }

    # Compact markdown comparison focused on assessable statements only.
    comparison_lines = [
        "# Ticket P5 Toy-vs-Vendor Comparison",
        "",
        "## Scope",
        "- Inputs: `data/pica_atlas/*`, `data/pica_normalized/*`, and existing toy reports (`results/ticket-05` through `results/ticket-06-4`).",
        "- Method: conservative support/provenance comparison only (no new runs, no claim promotion).",
        "",
        "## Comparison",
        "- baseline-like configs vs richer structured configs: **not_assessable_from_surface_presence**; quantitative deltas are required.",
        "- heterogeneous cell importance: **not_assessable_from_coverage_counts**; quantitative ablation deltas are required.",
        "- necessity of interaction structure: **not_assessable_from_surface_presence**; a substantive comparator test is required.",
        "- broad uniqueness/stability-style claims: **not_assessable_from_shipped_data** (toy falsification exists, but no direct normalized vendor metric mapping for full equivalence test).",
        "",
        "## Caution",
        "- Any statement above marked supported is support at the surface/provenance level, not a promoted theorem-level conclusion.",
    ]

    profiles_path = output_dir / "program_profiles.csv"
    ablations_path = output_dir / "ablation_summary.csv"
    survivor_path = output_dir / "survivor_failure_list.yaml"
    comparison_path = output_dir / "toy_vs_vendor_comparison.md"

    write_csv(profiles_path, profiles)
    write_csv(ablations_path, ablations)
    survivor_path.write_text(yaml.safe_dump(survivor_failure, sort_keys=False), encoding="utf-8")
    comparison_path.write_text("\n".join(comparison_lines) + "\n", encoding="utf-8")

    print(f"wrote {profiles_path}")
    print(f"wrote {ablations_path}")
    print(f"wrote {survivor_path}")
    print(f"wrote {comparison_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
