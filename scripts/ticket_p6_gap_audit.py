#!/usr/bin/env python3
from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent.parent

PROGRAM_ATLAS = ROOT / "data" / "pica_atlas" / "program_atlas.yaml"
FIGDATA_NORMALIZED = ROOT / "data" / "pica_normalized" / "figdata_records.jsonl"
P5_PROFILES = ROOT / "results" / "ticket-p5" / "program_profiles.csv"
P5_ABLATIONS = ROOT / "results" / "ticket-p5" / "ablation_summary.csv"
P5_SURVIVOR = ROOT / "results" / "ticket-p5" / "survivor_failure_list.yaml"

RUN_SUMMARY_GZ = ROOT / "vendors" / "six-birds-pica" / "paper" / "figdata" / "run_summary_table.csv.gz"
ROBUSTNESS_CSV = ROOT / "vendors" / "six-birds-pica" / "paper" / "figdata" / "T6_robustness.csv"


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected YAML mapping: {path}")
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


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_run_summary_configs(path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            cfg = (row.get("config_name") or "").strip()
            if not cfg:
                continue
            counts[cfg] = counts.get(cfg, 0) + 1
    return counts


def build_matrix() -> list[dict[str, str]]:
    program_atlas = load_yaml(PROGRAM_ATLAS)
    fig_norm = load_jsonl(FIGDATA_NORMALIZED)
    p5_profiles = load_csv(P5_PROFILES)
    p5_ablations = load_csv(P5_ABLATIONS)
    p5_survivor = load_yaml(P5_SURVIVOR)
    run_config_counts = load_run_summary_configs(RUN_SUMMARY_GZ)
    robustness_rows = load_csv(ROBUSTNESS_CSV)

    atlas_entries = [e for e in program_atlas.get("entries", []) if isinstance(e, dict)]
    atlas_labels = {str(e.get("label", "")) for e in atlas_entries}
    loo_labels = {lbl for lbl in atlas_labels if lbl.startswith("loo_")}
    row_group_count = sum(1 for e in atlas_entries if str(e.get("program_kind", "")) == "row_group")

    run_summary_present = any(str(r.get("surface_kind")) == "run_summary" for r in fig_norm)
    scan_present = any(str(r.get("surface_kind")) == "headline_metrics" for r in fig_norm)
    robustness_present = any(str(r.get("surface_kind")) == "robustness" for r in fig_norm)

    robustness_partial_checks = sum(1 for r in robustness_rows if (r.get("result_status") or "").strip() == "PARTIAL")
    has_baseline = "baseline" in run_config_counts
    has_full_action = "full_action" in run_config_counts
    has_full_all = "full_all" in run_config_counts
    has_pair_configs = any("_" in cfg and not cfg.startswith("loo_") for cfg in run_config_counts)

    p5_supported = p5_survivor.get("programs", {}).get("supported_by_vendor", [])
    supported_ids = {str(x.get("id", "")) for x in p5_supported if isinstance(x, dict)}

    matrix: list[dict[str, str]] = []
    matrix.append(
        {
            "question_class": "baseline_vs_richer_structured_configs",
            "status": "partially_answered_by_shipped_data",
            "supporting_surfaces": "run_summary_table.csv.gz; program_atlas.yaml; ticket-p5/program_profiles.csv",
            "main_blocker": "Quantitative superiority must be read from measured program deltas; config presence alone is insufficient.",
            "blocker_resolution": "parse_more_shipped_artifacts",
            "narrow_claim_relevance": "high",
        }
    )

    matrix.append(
        {
            "question_class": "heterogeneous_cell_importance",
            "status": "partially_answered_by_shipped_data",
            "supporting_surfaces": "loo_cell_map.csv; run_summary_table.csv.gz; ticket-p5/ablation_summary.csv",
            "main_blocker": "Current repository has coverage-based proxies, not direct per-cell quantitative effect deltas.",
            "blocker_resolution": "parse_more_shipped_artifacts",
            "narrow_claim_relevance": "high",
        }
    )

    matrix.append(
        {
            "question_class": "pairwise_multi_cell_interaction_evidence",
            "status": "partially_answered_by_shipped_data"
            if has_pair_configs
            else "unanswered",
            "supporting_surfaces": "run_summary_table.csv.gz config_name field; program_atlas.yaml row_group entries",
            "main_blocker": "Interaction gain over best strict subprogram is not yet quantified from shipped tables.",
            "blocker_resolution": "parse_more_shipped_artifacts" if has_pair_configs else "cheap_new_run",
            "narrow_claim_relevance": "high",
        }
    )

    matrix.append(
        {
            "question_class": "robustness_across_seeds_scales_scans",
            "status": "partially_answered_by_shipped_data"
            if (robustness_present or scan_present)
            else "unanswered",
            "supporting_surfaces": "T6_robustness.csv; run_summary_table.csv.gz; scan_rung_table.csv.gz",
            "main_blocker": f"Robustness table includes {robustness_partial_checks} PARTIAL checks, so support is incomplete.",
            "blocker_resolution": "parse_more_shipped_artifacts",
            "narrow_claim_relevance": "medium",
        }
    )

    matrix.append(
        {
            "question_class": "quantitative_effect_sizes_for_loo_ablations",
            "status": "partially_answered_by_shipped_data"
            if loo_labels
            else "unanswered",
            "supporting_surfaces": "loo_cell_map.csv; run_summary_table.csv.gz; ticket-p5/ablation_summary.csv",
            "main_blocker": "Effect sizes are not yet extracted in a dedicated LOO delta table in this repo.",
            "blocker_resolution": "parse_more_shipped_artifacts",
            "narrow_claim_relevance": "high",
        }
    )

    if {"toy_baseline_weaker_than_richer_configs", "toy_heterogeneous_cell_importance", "toy_interaction_structure_needed"} <= supported_ids:
        narrow_status = "partially_answered_by_shipped_data"
        narrow_blocker = "Support is surface-level; claim-grade quantitative interaction deltas remain unextracted."
        narrow_action = "parse_more_shipped_artifacts"
    else:
        narrow_status = "unanswered"
        narrow_blocker = "Baseline/richer/cell-heterogeneity support does not yet jointly pass even at surface level."
        narrow_action = "cheap_new_run"

    matrix.append(
        {
            "question_class": "support_for_narrow_interaction_claim",
            "status": narrow_status,
            "supporting_surfaces": "ticket-p5/survivor_failure_list.yaml; run_summary_table.csv.gz; T6_robustness.csv",
            "main_blocker": narrow_blocker,
            "blocker_resolution": narrow_action,
            "narrow_claim_relevance": "critical",
        }
    )

    theorem_status = "unanswered"
    theorem_blocker = (
        "Shipped artifacts do not yet provide theorem-facing uncertainty closure: no dedicated parsed interaction-gain table, "
        "and robustness has known partial checks."
    )
    theorem_action = "moderate_new_run"
    if row_group_count < 1:
        theorem_blocker = "No row/group structure available for theorem/hybrid decision."
        theorem_action = "cheap_new_run"

    matrix.append(
        {
            "question_class": "theorem_or_hybrid_paper_decision_readiness",
            "status": theorem_status,
            "supporting_surfaces": "ticket-p5 outputs; T6_robustness.csv; run_summary_table.csv.gz; program_atlas.yaml",
            "main_blocker": theorem_blocker,
            "blocker_resolution": theorem_action,
            "narrow_claim_relevance": "critical",
        }
    )

    return matrix


def write_matrix(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "question_class",
                "status",
                "supporting_surfaces",
                "main_blocker",
                "blocker_resolution",
                "narrow_claim_relevance",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_run_plan(path: Path, matrix: list[dict[str, str]]) -> None:
    unanswered = [row for row in matrix if row["status"] == "unanswered"]
    plan_items: list[dict[str, str]] = []
    for row in unanswered:
        action = row["blocker_resolution"]
        if action == "parse_more_shipped_artifacts":
            plan_items.append(
                {
                    "question_class": row["question_class"],
                    "next_action": "parse_more_shipped_artifacts",
                    "label": "extract_interaction_delta_tables",
                    "ambiguity_resolved": "Turns shipped config/ablation surfaces into explicit numeric deltas.",
                    "cost_class": "none",
                }
            )
        elif action == "cheap_new_run":
            plan_items.append(
                {
                    "question_class": row["question_class"],
                    "next_action": "cheap_new_run",
                    "label": "targeted_missing_config_replay",
                    "ambiguity_resolved": "Fills missing narrow interaction evidence on smallest unresolved configuration slice.",
                    "cost_class": "cheap_new_run",
                }
            )
        elif action == "moderate_new_run":
            plan_items.append(
                {
                    "question_class": row["question_class"],
                    "next_action": "moderate_new_run",
                    "label": "interaction_delta_confirmatory_grid",
                    "ambiguity_resolved": "Confirms interaction-gain and robustness with explicit subprogram baselines across seeds/scales.",
                    "cost_class": "moderate_new_run",
                }
            )
        else:
            plan_items.append(
                {
                    "question_class": row["question_class"],
                    "next_action": "none",
                    "label": "none",
                    "ambiguity_resolved": "No additional action required.",
                    "cost_class": "none",
                }
            )

    output = {
        "plan_id": "ticket_p6_additional_run_plan",
        "version": "0.1.0",
        "genuinely_unanswered_count": len(unanswered),
        "items": plan_items,
    }
    path.write_text(yaml.safe_dump(output, sort_keys=False), encoding="utf-8")


def write_report(path: Path, matrix: list[dict[str, str]]) -> None:
    status_counts: dict[str, int] = {
        "answered_by_shipped_data": 0,
        "partially_answered_by_shipped_data": 0,
        "unanswered": 0,
    }
    for row in matrix:
        status_counts[row["status"]] += 1

    narrow_row = next((row for row in matrix if row["question_class"] == "support_for_narrow_interaction_claim"), None)
    theorem_row = next((row for row in matrix if row["question_class"] == "theorem_or_hybrid_paper_decision_readiness"), None)

    lines = [
        "# Ticket P6 Gap Audit",
        "",
        "## Matrix totals",
        f"- answered_by_shipped_data: {status_counts['answered_by_shipped_data']}",
        f"- partially_answered_by_shipped_data: {status_counts['partially_answered_by_shipped_data']}",
        f"- unanswered: {status_counts['unanswered']}",
        "",
        "## Narrow interaction claim",
        f"- status: {narrow_row['status'] if narrow_row else 'unknown'}",
        f"- blocker: {narrow_row['main_blocker'] if narrow_row else 'unknown'}",
        "",
        "## Theorem/hybrid decision readiness",
        f"- status: {theorem_row['status'] if theorem_row else 'unknown'}",
        f"- blocker: {theorem_row['main_blocker'] if theorem_row else 'unknown'}",
        "",
        "## Conservative conclusion",
        "- Shipped artifacts are enough to support a narrow interaction claim only partially.",
        "- A theorem/hybrid paper decision is not yet ready from shipped artifacts alone.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    out_dir = ROOT / "results" / "ticket-p6"
    out_dir.mkdir(parents=True, exist_ok=True)

    matrix = build_matrix()
    write_matrix(out_dir / "answered_unanswered_matrix.csv", matrix)
    write_run_plan(out_dir / "additional_run_plan.yaml", matrix)
    write_report(out_dir / "report.md", matrix)

    print(f"wrote {out_dir / 'answered_unanswered_matrix.csv'}")
    print(f"wrote {out_dir / 'additional_run_plan.yaml'}")
    print(f"wrote {out_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
