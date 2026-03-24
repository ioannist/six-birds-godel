#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path
import re
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent.parent
RUN_BASE = ROOT / "vendors" / "six-birds-pica" / "lab" / "runs" / "ticket_p6_4"
RUN_DIRS = [RUN_BASE / "ticket_p6_4_primary", RUN_BASE / "ticket_p6_4a_resume"]
OUT_DIR = ROOT / "results" / "ticket-p6-4a"
GAP_SCAN = OUT_DIR / "gap_scan.yaml"

CONFIGS = ["A14_only", "baseline", "full_action", "full_all", "A13_A14", "A14_A19"]
PRIMARY_SCALES = [64, 128]
SEED_REQUIRED = 10
CANONICAL_METRIC = "delta_vs_baseline_frob_from_rank1"
RX = re.compile(r"EXP-112_s(?P<seed>\d+)_n(?P<scale>\d+)_(?P<config>.+)\.log$")


def parse_audit(path: Path) -> dict[str, Any] | None:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in reversed(lines):
        if line.startswith("KEY_AUDIT_JSON "):
            try:
                return json.loads(line[len("KEY_AUDIT_JSON ") :])
            except json.JSONDecodeError:
                return None
    return None


def has_k4(audit: dict[str, Any] | None) -> bool:
    if not isinstance(audit, dict):
        return False
    for item in audit.get("multi_scale_scan", []):
        if isinstance(item, dict) and item.get("k") == 4:
            return True
    return False


def mean(vals: list[float]) -> float | None:
    return sum(vals) / len(vals) if vals else None


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    latest: dict[tuple[str, int, int], dict[str, Any]] = {}
    for run_dir in RUN_DIRS:
        if not run_dir.exists():
            continue
        for p in run_dir.glob("EXP-112_s*_n*_*.log"):
            m = RX.match(p.name)
            if not m:
                continue
            seed = int(m.group("seed"))
            scale = int(m.group("scale"))
            config = m.group("config")
            if config not in CONFIGS or scale not in PRIMARY_SCALES:
                continue
            key = (config, scale, seed)
            prev = latest.get(key)
            if prev is not None and prev["mtime"] > p.stat().st_mtime:
                continue
            audit = parse_audit(p)
            latest[key] = {
                "config": config,
                "scale": scale,
                "seed": seed,
                "path": str(p.relative_to(ROOT)),
                "mtime": p.stat().st_mtime,
                "has_audit": audit is not None,
                "has_k4": has_k4(audit),
                "frob": None if audit is None else float(audit.get("frob_from_rank1", 0.0)),
            }

    parsed_rows = [v for v in latest.values() if v["has_audit"]]

    by_cfg_scale: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in parsed_rows:
        by_cfg_scale.setdefault((row["config"], row["scale"]), []).append(row)

    baseline_means: dict[int, float] = {}
    for n in PRIMARY_SCALES:
        vals = [r["frob"] for r in by_cfg_scale.get(("baseline", n), []) if r["frob"] is not None]
        m = mean(vals)
        if m is not None:
            baseline_means[n] = m

    means: dict[tuple[str, int], float] = {}
    for cfg in CONFIGS:
        for n in PRIMARY_SCALES:
            vals = [r["frob"] for r in by_cfg_scale.get((cfg, n), []) if r["frob"] is not None]
            m = mean(vals)
            if m is not None:
                means[(cfg, n)] = m

    out_rows: list[dict[str, Any]] = []
    for cfg in CONFIGS:
        for n in PRIMARY_SCALES:
            rows = by_cfg_scale.get((cfg, n), [])
            if not rows:
                continue
            cfg_mean = means[(cfg, n)]
            b = baseline_means.get(n)
            seed_count = len({r["seed"] for r in rows})
            anchor_ratio = sum(1 for r in rows if r["has_k4"]) / len(rows)
            flags = []
            if seed_count < SEED_REQUIRED:
                flags.append("incomplete_primary_seed_coverage")
            if anchor_ratio <= 0.0:
                flags.append("anchor_k4_missing")

            d = lambda other: "" if (other, n) not in means else round(cfg_mean - means[(other, n)], 8)
            out_rows.append(
                {
                    "config": cfg,
                    "scale": n,
                    "canonical_primary_metric_name": CANONICAL_METRIC,
                    "primary_metric_mean": round(cfg_mean, 8),
                    "delta_vs_baseline_frob_from_rank1": "" if b is None else round(cfg_mean - b, 8),
                    "delta_vs_A13_A14_frob_from_rank1": d("A13_A14"),
                    "delta_vs_A14_A19_frob_from_rank1": d("A14_A19"),
                    "delta_vs_full_action_frob_from_rank1": d("full_action"),
                    "delta_vs_full_all_frob_from_rank1": d("full_all"),
                    "seed_coverage_observed": seed_count,
                    "seed_coverage_required": SEED_REQUIRED,
                    "anchor_k4_coverage_ratio": round(anchor_ratio, 3),
                    "anchor_k4_pair_covered": anchor_ratio > 0.0,
                    "run_status_flags": "|".join(flags) if flags else "ok",
                }
            )

    gap = yaml.safe_load(GAP_SCAN.read_text(encoding="utf-8")) if GAP_SCAN.exists() else {}
    primary_complete = bool(gap.get("primary_coverage_complete_now", False))
    remaining_cells = [c for c in gap.get("cells", []) if c.get("remaining_required", 0) > 0]

    readiness = {
        "rescore_id": "ticket_p6_4a_readiness_rescore",
        "version": "0.1.0",
        "canonical_metric_name": CANONICAL_METRIC,
        "decision_logic_source": "results/ticket-p6-3/decision_logic.yaml",
        "thresholds_drifted": False,
        "primary_coverage_complete": primary_complete,
        "final_verdict": "hybrid_ready" if primary_complete else "not_ready",
        "a14_only_remains_focus": True,
        "remaining_gap_cells": [
            {
                "config": c.get("config"),
                "scale": c.get("scale"),
                "remaining_required": c.get("remaining_required"),
                "anchor_missing_count": c.get("anchor_missing_count"),
            }
            for c in remaining_cells
        ],
    }

    run_manifest = {
        "run_id": "ticket_p6_4a_resume",
        "version": "0.1.0",
        "exp_lineage": "EXP-112",
        "canonical_metric_name": CANONICAL_METRIC,
        "run_dirs_considered": [str(d.relative_to(ROOT)) for d in RUN_DIRS if d.exists()],
        "attempted_unique_cells_seen": len(latest),
        "parsed_completed_cells": len(parsed_rows),
        "primary_coverage_complete": primary_complete,
        "resume_jobs_remaining": int(gap.get("resume_job_count", 0)),
    }

    # Write files
    (OUT_DIR / "run_manifest.yaml").write_text(yaml.safe_dump(run_manifest, sort_keys=False), encoding="utf-8")
    with (OUT_DIR / "confirmatory_results.csv").open("w", encoding="utf-8", newline="") as h:
        if out_rows:
            w = csv.DictWriter(h, fieldnames=list(out_rows[0].keys()))
            w.writeheader()
            for r in sorted(out_rows, key=lambda x: (x["scale"], x["config"])):
                w.writerow(r)
        else:
            h.write("config,scale,canonical_primary_metric_name,run_status_flags\n")
    (OUT_DIR / "readiness_rescore.yaml").write_text(yaml.safe_dump(readiness, sort_keys=False), encoding="utf-8")

    report = [
        "# Ticket P6.4a Primary-Coverage Completion Rerun",
        "",
        f"- exp lineage: EXP-112",
        f"- canonical metric: {CANONICAL_METRIC}",
        f"- primary coverage complete: {'yes' if primary_complete else 'no'}",
        f"- final readiness verdict: {'hybrid_ready' if primary_complete else 'not_ready'}",
        f"- A14_only remains focus: yes",
        "",
        "If primary coverage remains incomplete, readiness is scored conservatively.",
    ]
    if remaining_cells:
        report.append("")
        report.append("Remaining gaps:")
        for c in remaining_cells:
            report.append(
                f"- {c.get('config')}@n={c.get('scale')}: remaining_required={c.get('remaining_required')}, anchor_missing_count={c.get('anchor_missing_count')}"
            )
    (OUT_DIR / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    print(f"wrote {OUT_DIR / 'run_manifest.yaml'}")
    print(f"wrote {OUT_DIR / 'confirmatory_results.csv'}")
    print(f"wrote {OUT_DIR / 'readiness_rescore.yaml'}")
    print(f"wrote {OUT_DIR / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
