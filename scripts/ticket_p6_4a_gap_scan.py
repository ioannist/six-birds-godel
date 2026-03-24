#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent.parent
RUN_BASE = ROOT / "vendors" / "six-birds-pica" / "lab" / "runs" / "ticket_p6_4"
RUN_DIRS = [RUN_BASE / "ticket_p6_4_primary", RUN_BASE / "ticket_p6_4a_resume"]
OUT_DIR = ROOT / "results" / "ticket-p6-4a"

CONFIGS = ["A14_only", "baseline", "full_action", "full_all", "A13_A14", "A14_A19"]
SCALES = [64, 128]
SEEDS = list(range(10))
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


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Keep newest record per (config, scale, seed) across both primary and resume dirs.
    state: dict[tuple[str, int, int], dict[str, Any]] = {}
    for run_dir in RUN_DIRS:
        if not run_dir.exists():
            continue
        for p in sorted(run_dir.glob("EXP-112_s*_n*_*.log")):
            m = RX.match(p.name)
            if not m:
                continue
            seed = int(m.group("seed"))
            scale = int(m.group("scale"))
            config = m.group("config")
            if config not in CONFIGS or scale not in SCALES:
                continue
            key = (config, scale, seed)
            prev = state.get(key)
            if prev is not None and prev["mtime"] > p.stat().st_mtime:
                continue
            audit = parse_audit(p)
            state[key] = {
                "log_path": str(p.relative_to(ROOT)),
                "has_audit": audit is not None,
                "has_anchor_k4": has_k4(audit),
                "file_size": p.stat().st_size,
                "mtime": p.stat().st_mtime,
            }

    missing_jobs: list[dict[str, Any]] = []
    missing_anchor_pairs: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "scan_id": "ticket_p6_4a_gap_scan",
        "version": "0.2.0",
        "exp_lineage": "EXP-112",
        "run_dirs_considered": [str(d.relative_to(ROOT)) for d in RUN_DIRS if d.exists()],
        "configs": CONFIGS,
        "scales": SCALES,
        "required_seeds_per_cell": len(SEEDS),
        "cells": [],
    }

    for config in CONFIGS:
        for scale in SCALES:
            good = []
            bad_anchor = []
            missing = []
            for seed in SEEDS:
                rec = state.get((config, scale, seed))
                if rec is None:
                    missing.append(seed)
                elif not rec["has_audit"]:
                    missing.append(seed)
                elif not rec["has_anchor_k4"]:
                    bad_anchor.append(seed)
                else:
                    good.append(seed)

            for seed in sorted(missing):
                missing_jobs.append(
                    {
                        "exp": "EXP-112",
                        "seed": seed,
                        "scale": scale,
                        "stage": "ticket_p6_4a_resume",
                        "config": config,
                        "env": {"SIX_BIRDS_AUDIT_RICH": "1"},
                    }
                )

            has_pair_anchor = len(good) > 0
            if not has_pair_anchor:
                missing_anchor_pairs.append({"config": config, "scale": scale, "required_anchor": "k_rung=4"})
                # Anchor rerun probe: use first available seed or seed 0 if none exists yet.
                anchor_seed = 0
                if bad_anchor:
                    anchor_seed = sorted(bad_anchor)[0]
                elif missing:
                    anchor_seed = sorted(missing)[0]
                missing_jobs.append(
                    {
                        "exp": "EXP-112",
                        "seed": anchor_seed,
                        "scale": scale,
                        "stage": "ticket_p6_4a_resume",
                        "config": config,
                        "env": {"SIX_BIRDS_AUDIT_RICH": "1"},
                        "reason": "anchor_k4_pair_missing",
                    }
                )

            summary["cells"].append(
                {
                    "config": config,
                    "scale": scale,
                    "good_seeds": sorted(good),
                    "good_seed_count": len(good),
                    "missing_or_no_audit_seeds": sorted(missing),
                    "missing_or_no_audit_count": len(missing),
                    "anchor_missing_seeds": sorted(bad_anchor),
                    "anchor_missing_count": len(bad_anchor),
                    "anchor_pair_covered": has_pair_anchor,
                    "remaining_required": len(missing) + (0 if has_pair_anchor else 1),
                }
            )

    summary["resume_job_count"] = len(missing_jobs)
    summary["missing_anchor_pairs"] = missing_anchor_pairs
    summary["primary_coverage_complete_now"] = len(missing_jobs) == 0

    (OUT_DIR / "gap_scan.yaml").write_text(yaml.safe_dump(summary, sort_keys=False), encoding="utf-8")
    (OUT_DIR / "jobs_resume_exp112.json").write_text(json.dumps(missing_jobs, indent=2), encoding="utf-8")

    print(f"wrote {OUT_DIR / 'gap_scan.yaml'}")
    print(f"wrote {OUT_DIR / 'jobs_resume_exp112.json'}")
    print(f"resume_jobs={len(missing_jobs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
