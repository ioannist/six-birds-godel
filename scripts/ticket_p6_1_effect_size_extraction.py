#!/usr/bin/env python3
from __future__ import annotations

import csv
import gzip
import math
from pathlib import Path
import statistics
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent.parent
FIGDATA_DIR = ROOT / "vendors" / "six-birds-pica" / "paper" / "figdata"

RUN_SUMMARY = FIGDATA_DIR / "run_summary_table.csv.gz"
SCAN_RUNG = FIGDATA_DIR / "scan_rung_table.csv.gz"
T6_ROBUSTNESS = FIGDATA_DIR / "T6_robustness.csv"
LOO_CELL_MAP = FIGDATA_DIR / "loo_cell_map.csv"
T3_HEADLINE = FIGDATA_DIR / "T3_headline_metrics.csv"
T5_CORR = FIGDATA_DIR / "T5_correlations_regression.csv"

PROGRAM_ATLAS = ROOT / "data" / "pica_atlas" / "program_atlas.yaml"
P5_PROFILES = ROOT / "results" / "ticket-p5" / "program_profiles.csv"
P6_MATRIX = ROOT / "results" / "ticket-p6" / "answered_unanswered_matrix.csv"

CORE_N = {64, 128}
CONTROL_N = {32}
EXTENDED_N = {256}
ALL_N = CORE_N | CONTROL_N | EXTENDED_N

METRICS = ("frob_from_rank1", "sigma_ratio", "macro_gap")


def parse_float(value: str) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        value = float(text)
        return value if math.isfinite(value) else None
    except ValueError:
        return None


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected YAML mapping: {path}")
    return data


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_csv_gz(path: Path) -> list[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def n_tier(n: int) -> str:
    if n in CORE_N:
        return "core"
    if n in CONTROL_N:
        return "control"
    if n in EXTENDED_N:
        return "extended"
    return "other"


def mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def stdev(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    return statistics.stdev(values)


def summarize_metric(rows: list[dict[str, str]], metric: str) -> tuple[float | None, int, float | None]:
    vals = [v for v in (parse_float(r.get(metric, "")) for r in rows) if v is not None]
    return mean(vals), len(vals), stdev(vals)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    out_dir = ROOT / "results" / "ticket-p6-1"
    out_dir.mkdir(parents=True, exist_ok=True)

    run_rows = load_csv_gz(RUN_SUMMARY)
    _scan_rows = load_csv_gz(SCAN_RUNG)
    t6_rows = load_csv(T6_ROBUSTNESS)
    loo_rows = load_csv(LOO_CELL_MAP)
    _t3_rows = load_csv(T3_HEADLINE)
    _t5_rows = load_csv(T5_CORR)

    atlas = load_yaml(PROGRAM_ATLAS)
    p5_profiles = load_csv(P5_PROFILES)
    p6_matrix = load_csv(P6_MATRIX)

    by_config_n: dict[tuple[str, int], list[dict[str, str]]] = {}
    for row in run_rows:
        cfg = (row.get("config_name") or "").strip()
        n_val = row.get("n") or ""
        try:
            n = int(n_val)
        except ValueError:
            continue
        if not cfg or n not in ALL_N:
            continue
        by_config_n.setdefault((cfg, n), []).append(row)

    baseline_by_n: dict[int, list[dict[str, str]]] = {n: by_config_n.get(("baseline", n), []) for n in ALL_N}
    full_all_by_n: dict[int, list[dict[str, str]]] = {n: by_config_n.get(("full_all", n), []) for n in ALL_N}

    # Program set: baseline/full presets + all LOO + high-support row/group from P5.
    selected_configs: set[str] = {"baseline", "full_action", "full_all"}
    for row in p5_profiles:
        label = row.get("label", "")
        kind = row.get("program_kind", "")
        support = row.get("support_class", "")
        if label.startswith("loo_"):
            selected_configs.add(label)
            continue
        if kind == "row_group" and support in {"strong_surface_support", "moderate_surface_support"}:
            selected_configs.add(label)

    # Program effect sizes
    program_rows: list[dict[str, Any]] = []
    for cfg in sorted(selected_configs):
        for n in sorted(ALL_N):
            rows = by_config_n.get((cfg, n), [])
            if not rows:
                continue
            for metric in METRICS:
                cfg_mean, cfg_count, _ = summarize_metric(rows, metric)
                base_mean, _, base_std = summarize_metric(baseline_by_n.get(n, []), metric)
                if cfg_mean is None or base_mean is None:
                    continue
                delta = cfg_mean - base_mean
                z_like = None
                if base_std is not None and base_std > 0:
                    z_like = delta / base_std
                program_rows.append(
                    {
                        "config_name": cfg,
                        "n": n,
                        "n_tier": n_tier(n),
                        "metric": metric,
                        "config_mean": round(cfg_mean, 8),
                        "baseline_mean": round(base_mean, 8),
                        "delta_vs_baseline": round(delta, 8),
                        "delta_vs_baseline_std_units": "" if z_like is None else round(z_like, 8),
                        "sample_count": cfg_count,
                        "insufficient_if_control_only": int(n in CONTROL_N),
                    }
                )

    # LOO cell effect sizes vs full_all and baseline.
    loo_map: dict[str, dict[str, str]] = {}
    for row in loo_rows:
        cfg = (row.get("config_name") or "").strip()
        if cfg:
            loo_map[cfg] = row

    cell_rows: list[dict[str, Any]] = []
    for loo_cfg in sorted(loo_map.keys()):
        for n in sorted(ALL_N):
            loo_data = by_config_n.get((loo_cfg, n), [])
            if not loo_data:
                continue
            full_all_data = full_all_by_n.get(n, [])
            base_data = baseline_by_n.get(n, [])
            for metric in METRICS:
                loo_mean, loo_count, _ = summarize_metric(loo_data, metric)
                full_mean, _, _ = summarize_metric(full_all_data, metric)
                base_mean, _, _ = summarize_metric(base_data, metric)
                if loo_mean is None:
                    continue
                delta_full = None if full_mean is None else loo_mean - full_mean
                delta_base = None if base_mean is None else loo_mean - base_mean
                cell_rows.append(
                    {
                        "loo_config": loo_cfg,
                        "cell_label": loo_map[loo_cfg].get("cell_label", ""),
                        "actor": loo_map[loo_cfg].get("actor", ""),
                        "informant": loo_map[loo_cfg].get("informant", ""),
                        "n": n,
                        "n_tier": n_tier(n),
                        "metric": metric,
                        "loo_mean": round(loo_mean, 8),
                        "full_all_mean": "" if full_mean is None else round(full_mean, 8),
                        "baseline_mean": "" if base_mean is None else round(base_mean, 8),
                        "delta_vs_full_all": "" if delta_full is None else round(delta_full, 8),
                        "delta_vs_baseline": "" if delta_base is None else round(delta_base, 8),
                        "sample_count": loo_count,
                        "insufficient_if_control_only": int(n in CONTROL_N),
                    }
                )

    # Build atlas label -> member-cells for simpler-subprogram lookup.
    atlas_entries = [e for e in atlas.get("entries", []) if isinstance(e, dict)]
    members_by_label: dict[str, set[str]] = {}
    for entry in atlas_entries:
        lbl = str(entry.get("label", "")).strip()
        if not lbl:
            continue
        cells = {str(c) for c in entry.get("member_cells", []) if isinstance(c, str)}
        members_by_label[lbl] = cells

    # Interaction deltas for multi-cell configs.
    interaction_rows: list[dict[str, Any]] = []
    multi_configs = [
        cfg
        for cfg in sorted(selected_configs)
        if cfg in members_by_label and len(members_by_label[cfg]) >= 2 and cfg not in {"baseline"}
    ]

    for cfg in multi_configs:
        cfg_cells = members_by_label.get(cfg, set())
        nearest = sorted(
            (cand for cand, cells in members_by_label.items() if cells and cells < cfg_cells),
            key=lambda cand: (-len(members_by_label[cand]), cand),
        )
        nearest_label = nearest[0] if nearest else ""
        for n in sorted(ALL_N):
            cfg_data = by_config_n.get((cfg, n), [])
            base_data = baseline_by_n.get(n, [])
            if not cfg_data or not base_data:
                continue

            cfg_mean, cfg_count, _ = summarize_metric(cfg_data, "frob_from_rank1")
            base_mean, _, _ = summarize_metric(base_data, "frob_from_rank1")
            if cfg_mean is None or base_mean is None:
                continue
            delta_vs_base = cfg_mean - base_mean

            # Preserve the declared nearest nonempty subprogram comparison.
            # Audit the stronger best-measured-subprogram claim separately.
            simpler_options = []
            unmeasured = 0
            for cand, cand_cells in members_by_label.items():
                if not cand_cells < cfg_cells:
                    continue
                cand_mean, _, _ = summarize_metric(by_config_n.get((cand, n), []), "frob_from_rank1")
                if cand_mean is None:
                    unmeasured += 1
                else:
                    simpler_options.append((abs(cand_mean - base_mean), cand, cand_mean))
            simpler_options.sort(key=lambda entry: (-entry[0], entry[1]))
            simpler_label = nearest_label
            simpler_mean, _, _ = summarize_metric(by_config_n.get((simpler_label, n), []), "frob_from_rank1")
            comparison_status = "resolved" if simpler_mean is not None else "unresolved"
            simpler_delta_vs_base = None if simpler_mean is None else simpler_mean - base_mean
            interaction_delta = (None if simpler_delta_vs_base is None else
                                 abs(delta_vs_base) - abs(simpler_delta_vs_base))

            interaction_rows.append(
                {
                    "config_name": cfg,
                    "n": n,
                    "n_tier": n_tier(n),
                    "member_cell_count": len(cfg_cells),
                    "closest_simpler_config": simpler_label,
                    "config_mean_frob_from_rank1": round(cfg_mean, 8),
                    "baseline_mean_frob_from_rank1": round(base_mean, 8),
                    "delta_vs_baseline": round(delta_vs_base, 8),
                    "simpler_mean_frob_from_rank1": "" if simpler_mean is None else round(simpler_mean, 8),
                    "simpler_delta_vs_baseline": "" if simpler_delta_vs_base is None else round(simpler_delta_vs_base, 8),
                    "interaction_delta_abs_shift": "" if interaction_delta is None else round(interaction_delta, 8),
                    "comparison_status": comparison_status,
                    "comparison_scope": "nearest_nonempty_shipped_strict_subprogram",
                    "best_absolute_shift_subprogram": simpler_options[0][1] if simpler_options else "",
                    "gain_over_best_absolute_shift": "" if not simpler_options else round(abs(delta_vs_base) - simpler_options[0][0], 8),
                    "best_comparison_scope": "all_measured_shipped_strict_subprograms_including_empty",
                    "unmeasured_strict_subprogram_count": unmeasured,
                    "sample_count": cfg_count,
                    "insufficient_if_control_only": int(n in CONTROL_N),
                }
            )

    # Decision readiness update focused on P6 open classes.
    prior_by_class = {row.get("question_class", ""): row.get("status", "") for row in p6_matrix}
    resolved_interaction_core = sum(
        1
        for row in interaction_rows
        if row["comparison_status"] == "resolved" and row["n_tier"] == "core"
    )
    core_cell_effect_rows = sum(1 for row in cell_rows if row["n_tier"] == "core")
    unresolved_interaction_core = sum(
        1
        for row in interaction_rows
        if row["comparison_status"] == "unresolved" and row["n_tier"] == "core"
    )
    positive_best_core = sum(
        1 for row in interaction_rows
        if row["n_tier"] == "core" and row["gain_over_best_absolute_shift"] != ""
        and float(row["gain_over_best_absolute_shift"]) > 0
    )

    robust_partial_count = sum(1 for row in t6_rows if (row.get("result_status") or "").strip() == "PARTIAL")

    updates = [
        {
            "question_class": "pairwise_multi_cell_interaction_evidence",
            "prior_status": prior_by_class.get("pairwise_multi_cell_interaction_evidence", "unknown"),
            "updated_status": "partially_answered_by_shipped_data" if resolved_interaction_core > 0 else "unanswered",
            "basis": f"resolved_core_comparisons={resolved_interaction_core}; unresolved_core_comparisons={unresolved_interaction_core}",
        },
        {
            "question_class": "quantitative_effect_sizes_for_loo_ablations",
            "prior_status": prior_by_class.get("quantitative_effect_sizes_for_loo_ablations", "unknown"),
            "updated_status": "answered_by_shipped_data" if core_cell_effect_rows > 0 else "unanswered",
            "basis": f"core_cell_effect_rows={core_cell_effect_rows}",
        },
        {
            "question_class": "support_for_narrow_interaction_claim",
            "prior_status": prior_by_class.get("support_for_narrow_interaction_claim", "unknown"),
            "updated_status": "partially_answered_by_shipped_data",
            "basis": f"Nearest-subprogram deltas are descriptive; positive gains over the best measured strict subprogram at primary scales={positive_best_core}.",
        },
        {
            "question_class": "theorem_or_hybrid_paper_decision_readiness",
            "prior_status": prior_by_class.get("theorem_or_hybrid_paper_decision_readiness", "unknown"),
            "updated_status": "partially_answered_by_shipped_data",
            "basis": f"Descriptive deltas extracted; robustness_partial_checks={robust_partial_count}; unresolved nearest comparisons={unresolved_interaction_core}; positive best-subprogram gains={positive_best_core}.",
        },
    ]

    core_interaction_resolved = [
        row
        for row in interaction_rows
        if row["n_tier"] == "core" and row["comparison_status"] == "resolved" and row["interaction_delta_abs_shift"] != ""
    ]
    strongest_signal = "none"
    if core_interaction_resolved:
        best = max(core_interaction_resolved, key=lambda r: float(r["interaction_delta_abs_shift"]))
        strongest_signal = (
            f"{best['config_name']}@n={best['n']} interaction_delta_abs_shift={best['interaction_delta_abs_shift']}"
        )

    moderate_run_needed = "partial"
    # Parse-more-first succeeded; run is only for closing remaining unresolved theorem-grade gap.

    readiness = {
        "update_id": "ticket_p6_1_decision_readiness",
        "version": "0.1.0",
        "scale_rule": {
            "control": [32],
            "core": [64, 128],
            "extended": [256],
            "note": "Conclusions must not rely only on n=32.",
        },
        "question_updates": updates,
        "summary": {
            "moderate_new_run_still_needed": moderate_run_needed,
            "core_resolved_interaction_comparisons": resolved_interaction_core,
            "core_unresolved_interaction_comparisons": unresolved_interaction_core,
            "core_cell_effect_rows": core_cell_effect_rows,
            "robustness_partial_checks": robust_partial_count,
            "strongest_shipped_interaction_signal": strongest_signal,
            "strongest_signal_scope": "nearest_nonempty_shipped_strict_subprogram",
            "positive_best_subprogram_core_comparisons": positive_best_core,
        },
    }

    # Report
    lines = [
        "# Ticket P6.1 Shipped Effect-Size Extraction",
        "",
        "## Scale policy",
        "- n=32 treated as control only.",
        "- Decision-weighted analysis centered on n=64 and n=128.",
        "- n=256 included where shipped support exists.",
        "",
        "## Extraction status",
        f"- program_effect_sizes rows: {len(program_rows)}",
        f"- cell_effect_sizes rows: {len(cell_rows)}",
        f"- interaction_delta rows: {len(interaction_rows)}",
        "",
        "## Decision-gap update",
        f"- moderate_new_run_still_needed: {moderate_run_needed}",
        f"- strongest shipped interaction signal: {strongest_signal}",
        f"- unresolved core interaction comparisons: {unresolved_interaction_core}",
        "",
        "## Conservative note",
        "- Any signal driven only by n=32 is flagged as insufficient for decision-grade conclusions.",
        "- The original nearest-nonempty comparison is retained. Separate columns audit the best measured strict subprogram including the empty control.",
        "- Unmeasured subsets are counted; local gains are not a global synergy theorem.",
    ]

    write_csv(out_dir / "program_effect_sizes.csv", program_rows)
    write_csv(out_dir / "cell_effect_sizes.csv", cell_rows)
    write_csv(out_dir / "interaction_delta_table.csv", interaction_rows)
    (out_dir / "decision_readiness_update.yaml").write_text(
        yaml.safe_dump(readiness, sort_keys=False), encoding="utf-8"
    )
    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"wrote {out_dir / 'cell_effect_sizes.csv'}")
    print(f"wrote {out_dir / 'program_effect_sizes.csv'}")
    print(f"wrote {out_dir / 'interaction_delta_table.csv'}")
    print(f"wrote {out_dir / 'decision_readiness_update.yaml'}")
    print(f"wrote {out_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
