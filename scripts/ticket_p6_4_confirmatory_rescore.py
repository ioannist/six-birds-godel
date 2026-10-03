#!/usr/bin/env python3
from __future__ import annotations

import csv
from pathlib import Path
import re
import sys
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "python"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from closure_frontier.confirmatory import read_exp112_audit, has_k4, confirmatory_readiness

RUN_DIR = ROOT / "vendors" / "six-birds-pica" / "lab" / "runs" / "ticket_p6_4" / "ticket_p6_4_primary"
OUT_DIR = ROOT / "results" / "ticket-p6-4"

CONFIGS = ["A14_only", "baseline", "full_action", "full_all", "A13_A14", "A14_A19"]
PRIMARY_SCALES = [64, 128]
OPTIONAL_SCALES = [256]
SEED_REQUIRED = 10
CANONICAL_METRIC = "delta_vs_baseline_frob_from_rank1"

LOG_RE = re.compile(r"EXP-112_s(?P<seed>\d+)_n(?P<scale>\d+)_(?P<config>.+)\.log$")


parse_audit_from_log = read_exp112_audit

def mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Parse all attempted logs for EXP-112 subset.
    parsed_rows: list[dict[str, Any]] = []
    attempted_rows: list[dict[str, Any]] = []

    for log_path in sorted(RUN_DIR.glob("EXP-112_s*_n*_*.log")):
        m = LOG_RE.search(log_path.name)
        if not m:
            continue
        seed = int(m.group("seed"))
        scale = int(m.group("scale"))
        config = m.group("config")
        if config not in CONFIGS or scale not in PRIMARY_SCALES + OPTIONAL_SCALES or seed not in range(10):
            continue

        attempted_rows.append({"config": config, "scale": scale, "seed": seed, "log_path": str(log_path.relative_to(ROOT))})
        audit = parse_audit_from_log(log_path)
        if audit is None:
            continue

        # Anchor coverage from multi-scale scan k=4.
        k4_present = has_k4(audit)

        parsed_rows.append(
            {
                "config": config,
                "scale": scale,
                "seed": seed,
                "frob_from_rank1": float(audit["frob_from_rank1"]),
                "anchor_k4_present": k4_present,
                "run_status": "ok",
                "log_path": str(log_path.relative_to(ROOT)),
            }
        )

    # Aggregate by config/scale.
    by_cfg_scale: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in parsed_rows:
        by_cfg_scale.setdefault((row["config"], row["scale"]), []).append(row)

    baseline_mean_by_scale: dict[int, float] = {}
    for s in PRIMARY_SCALES + OPTIONAL_SCALES:
        vals = [r["frob_from_rank1"] for r in by_cfg_scale.get(("baseline", s), [])]
        m = mean(vals)
        if m is not None:
            baseline_mean_by_scale[s] = m

    comparator_means: dict[tuple[str, int], float] = {}
    for cfg in CONFIGS:
        for s in PRIMARY_SCALES + OPTIONAL_SCALES:
            vals = [r["frob_from_rank1"] for r in by_cfg_scale.get((cfg, s), [])]
            m = mean(vals)
            if m is not None:
                comparator_means[(cfg, s)] = m

    confirm_rows: list[dict[str, Any]] = []
    for cfg in CONFIGS:
        for s in PRIMARY_SCALES + OPTIONAL_SCALES:
            rows = by_cfg_scale.get((cfg, s), [])
            if not rows:
                continue
            cfg_mean = mean([r["frob_from_rank1"] for r in rows])
            if cfg_mean is None:
                continue
            baseline_mean = baseline_mean_by_scale.get(s)
            delta_vs_baseline = None if baseline_mean is None else cfg_mean - baseline_mean

            d_a13 = None
            d_a14a19 = None
            d_fa = None
            d_fall = None
            if ("A13_A14", s) in comparator_means:
                d_a13 = cfg_mean - comparator_means[("A13_A14", s)]
            if ("A14_A19", s) in comparator_means:
                d_a14a19 = cfg_mean - comparator_means[("A14_A19", s)]
            if ("full_action", s) in comparator_means:
                d_fa = cfg_mean - comparator_means[("full_action", s)]
            if ("full_all", s) in comparator_means:
                d_fall = cfg_mean - comparator_means[("full_all", s)]

            seed_count = len({r["seed"] for r in rows})
            anchor_ratio = sum(1 for r in rows if r["anchor_k4_present"]) / len(rows)

            flags: list[str] = []
            if s in PRIMARY_SCALES and seed_count < SEED_REQUIRED:
                flags.append("incomplete_primary_seed_coverage")
            if anchor_ratio < 1.0:
                flags.append("anchor_k4_missing")

            confirm_rows.append(
                {
                    "config": cfg,
                    "scale": s,
                    "canonical_primary_metric_name": CANONICAL_METRIC,
                    "primary_metric_mean": round(cfg_mean, 8),
                    "delta_vs_baseline_frob_from_rank1": "" if delta_vs_baseline is None else round(delta_vs_baseline, 8),
                    "delta_vs_A13_A14_frob_from_rank1": "" if d_a13 is None else round(d_a13, 8),
                    "delta_vs_A14_A19_frob_from_rank1": "" if d_a14a19 is None else round(d_a14a19, 8),
                    "delta_vs_full_action_frob_from_rank1": "" if d_fa is None else round(d_fa, 8),
                    "delta_vs_full_all_frob_from_rank1": "" if d_fall is None else round(d_fall, 8),
                    "seed_coverage_observed": seed_count,
                    "seed_coverage_required": SEED_REQUIRED if s in PRIMARY_SCALES else "optional",
                    "anchor_k4_coverage_ratio": round(anchor_ratio, 3),
                    "run_status_flags": "|".join(flags) if flags else "ok",
                }
            )

    decision = confirmatory_readiness(confirm_rows)
    primary_coverage_ok = decision["primary_coverage_complete"]
    verdict = decision["final_verdict"]
    a14_focus = decision["a14_only_remains_focus"]

    run_manifest = {
        "run_id": "ticket_p6_4_confirmatory",
        "version": "0.1.0",
        "canonical_metric_name": CANONICAL_METRIC,
        "attempted_jobs": len(attempted_rows),
        "parsed_completed_jobs": len(parsed_rows),
        "configs": CONFIGS,
        "primary_scales": PRIMARY_SCALES,
        "optional_scales": OPTIONAL_SCALES,
        "primary_seed_requirement": SEED_REQUIRED,
        "primary_coverage_complete": primary_coverage_ok,
        "notes": [
            "Initial EXP-107 launch was config-mismatched for A14 comparators and was superseded by EXP-112 run manifest.",
            "Readiness scoring is conservative: incomplete primary seed coverage forces not_ready.",
        ],
    }

    readiness = {
        "rescore_id": "ticket_p6_4_readiness_rescore",
        "version": "0.1.0",
        "canonical_metric_name": CANONICAL_METRIC,
        "primary_coverage_complete": primary_coverage_ok,
        "decision_logic_source": "results/ticket-p6-3/decision_logic.yaml",
        "thresholds_drifted": False,
        "final_verdict": verdict,
        "a14_only_remains_focus": bool(a14_focus),
        "run_status": "incomplete_primary_coverage" if not primary_coverage_ok else "complete",
    }

    readiness.update(decision)

    # Write outputs.
    (OUT_DIR / "run_manifest.yaml").write_text(yaml.safe_dump(run_manifest, sort_keys=False), encoding="utf-8")

    with (OUT_DIR / "confirmatory_results.csv").open("w", encoding="utf-8", newline="") as handle:
        if confirm_rows:
            writer = csv.DictWriter(handle, fieldnames=list(confirm_rows[0].keys()))
            writer.writeheader()
            for row in sorted(confirm_rows, key=lambda r: (r["scale"], r["config"])):
                writer.writerow(row)
        else:
            handle.write("config,scale,canonical_primary_metric_name,run_status_flags\n")

    (OUT_DIR / "readiness_rescore.yaml").write_text(yaml.safe_dump(readiness, sort_keys=False), encoding="utf-8")

    report_lines = [
        "# Ticket P6.4 Confirmatory Run and Rescore",
        "",
        f"- canonical metric name: {CANONICAL_METRIC}",
        f"- attempted jobs: {len(attempted_rows)}",
        f"- parsed completed jobs: {len(parsed_rows)}",
        f"- required primary coverage complete: {'yes' if primary_coverage_ok else 'no'}",
        f"- final readiness verdict: {verdict}",
        f"- A14_only remains focus: {'yes' if a14_focus else 'no'}",
        "",
        "Readiness applies the frozen signal, comparator, robustness, and per-seed rung coverage rules.",
    ]
    (OUT_DIR / "report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(f"wrote {OUT_DIR / 'run_manifest.yaml'}")
    print(f"wrote {OUT_DIR / 'confirmatory_results.csv'}")
    print(f"wrote {OUT_DIR / 'readiness_rescore.yaml'}")
    print(f"wrote {OUT_DIR / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
