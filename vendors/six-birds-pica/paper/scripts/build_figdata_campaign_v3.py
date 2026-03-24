#!/usr/bin/env python3
"""Build canonical paper figdata from campaign_v3 audits using a manifest."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

sys.path.append(str(Path(__file__).resolve().parent))
from plot_common import map_to_nearest_rung, rungs_for_n


SCAN_COLUMNS = [
    "exp_id",
    "config_name",
    "n",
    "seed",
    "tau",
    "active_tau",
    "log_file",
    "k_eff",
    "k_rung",
    "k_logdist",
    "frob",
    "sigma_pi",
    "step_entropy",
    "pla2_gap",
    "lagr_geo_r2",
    "lagr_diff_kl",
    "lagr_diff_alpha",
    "t_rel",
    "gap_ratio",
    "eigen_entropy",
    "spectral_participation",
    "slow_modes_r50",
    "slow_modes_r70",
    "slow_modes_r90",
]

RUN_COLUMNS = [
    "exp_id",
    "config_name",
    "n",
    "seed",
    "tau",
    "active_tau",
    "log_file",
    "sigma",
    "sigma_u",
    "sigma_ratio",
    "frob_from_rank1",
    "macro_gap",
    "cyc_max",
    "n_chiral",
    "n_absorb",
    "trans_ep",
    "n_trans",
    "tilde_frob",
    "tilde_sigma_pi",
    "tilde_step_entropy",
    "tilde_pla2_gap",
    "tilde_geo_r2",
    "tilde_diff_kl",
    "tilde_diff_alpha",
    "k_points_core",
    "is_REV",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build figdata from audits_all.jsonl + dataset manifest.")
    p.add_argument("--audits", default="lab/runs/campaign_v3/audits_all.jsonl")
    p.add_argument("--manifest", default="paper/figdata/paper_dataset_manifest.json")
    p.add_argument("--outdir", default="paper/figdata")
    p.add_argument("--force", action="store_true")
    return p.parse_args()


def to_float(value: object) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        out = float(value)
    elif isinstance(value, str):
        try:
            out = float(value)
        except ValueError:
            return None
    else:
        return None
    if not math.isfinite(out):
        return None
    return out


def to_int(value: object) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return None
    return None


def median_or_none(values: Iterable[Optional[float]]) -> Optional[float]:
    clean = [v for v in values if v is not None and math.isfinite(v)]
    if not clean:
        return None
    return float(statistics.median(clean))


def write_csv_gz(path: Path, rows: List[Dict[str, object]], columns: Sequence[str]) -> None:
    with gzip.open(path, "wt", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(columns))
        writer.writeheader()
        for row in rows:
            out = {}
            for col in columns:
                val = row.get(col)
                out[col] = "" if val is None else val
            writer.writerow(out)


def get_git_sha() -> Optional[str]:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return None


def matches_filter(rec: Dict[str, object], filt: Dict[str, object], exclude_waves: Sequence[str]) -> bool:
    exp_id = rec.get("exp_id")
    config_name = rec.get("config_name")
    n_val = rec.get("n")
    log_file = str(rec.get("_log_file") or "")

    if "exp_id" in filt and exp_id != filt["exp_id"]:
        return False
    if "n" in filt and n_val != filt["n"]:
        return False
    if "n_in" in filt:
        if n_val not in set(filt["n_in"]):
            return False
    if "log_file_contains" in filt and str(filt["log_file_contains"]) not in log_file:
        return False
    if "config_name_in" in filt and config_name not in set(filt["config_name_in"]):
        return False
    if "config_name_not_in" in filt and config_name in set(filt["config_name_not_in"]):
        return False
    if "exclude_config_name_in" in filt and config_name in set(filt["exclude_config_name_in"]):
        return False

    for wave in exclude_waves:
        token = f"/{wave}/"
        if token in log_file:
            return False
    return True


def summarize_seed_counts(counts: List[int]) -> Dict[str, Optional[float]]:
    if not counts:
        return {"groups": 0, "min": None, "median": None, "max": None}
    return {
        "groups": len(counts),
        "min": int(min(counts)),
        "median": float(statistics.median(counts)),
        "max": int(max(counts)),
    }


def main() -> int:
    args = parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    scan_out = outdir / "scan_rung_table.csv.gz"
    run_out = outdir / "run_summary_table.csv.gz"
    report_out = outdir / "figdata_build_report.json"

    if not args.force:
        for p in (scan_out, run_out, report_out):
            if p.exists():
                raise SystemExit(f"Output exists: {p} (use --force to overwrite)")

    audits_path = Path(args.audits)
    manifest_path = Path(args.manifest)
    if not audits_path.exists():
        raise SystemExit(f"Missing audits input: {audits_path}")
    if not manifest_path.exists():
        raise SystemExit(f"Missing manifest input: {manifest_path}")

    with manifest_path.open("r", encoding="utf-8") as fh:
        manifest = json.load(fh)

    datasets = manifest.get("datasets")
    if not isinstance(datasets, dict) or not datasets:
        raise SystemExit("Manifest must contain non-empty 'datasets' object.")

    exclusions = manifest.get("exclusions", {})
    exclude_waves = exclusions.get("exclude_waves", [])
    if not isinstance(exclude_waves, list):
        exclude_waves = []

    records: List[Dict[str, object]] = []
    with audits_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    selected_by_dataset: Dict[str, List[Dict[str, object]]] = {}
    for dataset_id in sorted(datasets.keys()):
        dataset_spec = datasets[dataset_id]
        filt = dataset_spec.get("filters", {})
        if not isinstance(filt, dict):
            raise SystemExit(f"Dataset {dataset_id} has invalid filters.")
        selected_by_dataset[dataset_id] = [
            r for r in records if matches_filter(r, filt, exclude_waves)
        ]

    # Union selected records with hard-fail duplicate identity check.
    selected_map: Dict[Tuple[str, int, int, str], Dict[str, object]] = {}
    selected_origin: Dict[Tuple[str, int, int, str], str] = {}
    duplicate_conflicts: List[Tuple[Tuple[str, int, int, str], str, str]] = []

    for dataset_id in sorted(selected_by_dataset.keys()):
        for rec in selected_by_dataset[dataset_id]:
            exp_id = rec.get("exp_id")
            n_val = to_int(rec.get("n"))
            seed = to_int(rec.get("seed"))
            config_name = rec.get("config_name")
            if not isinstance(exp_id, str) or not isinstance(config_name, str) or n_val is None or seed is None:
                raise SystemExit(
                    f"Record missing identity fields under dataset {dataset_id}: "
                    f"exp_id={exp_id}, config_name={config_name}, n={rec.get('n')}, seed={rec.get('seed')}"
                )
            key = (exp_id, n_val, seed, config_name)
            if key in selected_map:
                duplicate_conflicts.append((key, selected_origin[key], dataset_id))
                continue
            selected_map[key] = rec
            selected_origin[key] = dataset_id

    if duplicate_conflicts:
        preview = "\n".join(
            f"  {k} in {a} and {b}" for k, a, b in duplicate_conflicts[:10]
        )
        raise SystemExit(
            "Duplicate selected run identity (exp_id,n,seed,config_name) across manifest datasets.\n"
            + preview
        )

    selected_records = [selected_map[k] for k in sorted(selected_map.keys())]

    wave1_leaks = [
        r for r in selected_records if "/wave_1/" in str(r.get("_log_file") or "")
    ]
    if wave1_leaks:
        raise SystemExit(f"Selected records include excluded wave_1 rows: {len(wave1_leaks)}")

    missing_scan = [
        (r.get("exp_id"), r.get("config_name"), r.get("n"), r.get("seed"))
        for r in selected_records
        if not isinstance(r.get("multi_scale_scan"), list)
    ]
    if missing_scan:
        preview = "\n".join(f"  {x}" for x in missing_scan[:10])
        raise SystemExit(
            f"Found {len(missing_scan)} selected records without multi_scale_scan.\n{preview}"
        )

    scan_rows: List[Dict[str, object]] = []
    run_rows: List[Dict[str, object]] = []

    for run_id in sorted(selected_map.keys()):
        exp_id, n_val, seed, config_name = run_id
        obj = selected_map[run_id]

        tau = to_int(obj.get("tau"))
        active_tau = to_int(obj.get("active_tau"))
        log_file = str(obj.get("_log_file") or "")

        rungs = rungs_for_n(n_val)
        scan_entries = obj.get("multi_scale_scan")
        assert isinstance(scan_entries, list)

        best_for_rung: Dict[int, Dict[str, object]] = {}
        best_rank_for_rung: Dict[int, Tuple[float, float]] = {}

        for entry in scan_entries:
            if not isinstance(entry, dict):
                continue
            k_eff = to_float(entry.get("k"))
            if k_eff is None or k_eff <= 0.0 or not rungs:
                continue
            rung = map_to_nearest_rung(k_eff, rungs)
            if rung is None:
                continue
            logdist = abs(math.log2(k_eff) - math.log2(rung))
            rank = (logdist, k_eff)  # deterministic tie-breaker (smaller k_eff wins)
            prev_rank = best_rank_for_rung.get(rung)
            if prev_rank is not None and rank >= prev_rank:
                continue
            best_rank_for_rung[rung] = rank
            best_for_rung[rung] = {
                "exp_id": exp_id,
                "config_name": config_name,
                "n": n_val,
                "seed": seed,
                "tau": tau,
                "active_tau": active_tau,
                "log_file": log_file,
                "k_eff": k_eff,
                "k_rung": rung,
                "k_logdist": logdist,
                "frob": to_float(entry.get("frob")),
                "sigma_pi": to_float(entry.get("sigma_pi")),
                "step_entropy": to_float(entry.get("step_entropy")),
                "pla2_gap": to_float(entry.get("pla2_gap")),
                "lagr_geo_r2": to_float(entry.get("lagr_geo_r2")),
                "lagr_diff_kl": to_float(entry.get("lagr_diff_kl")),
                "lagr_diff_alpha": to_float(entry.get("lagr_diff_alpha")),
                "t_rel": to_float(entry.get("t_rel")),
                "gap_ratio": to_float(entry.get("gap_ratio")),
                "eigen_entropy": to_float(entry.get("eigen_entropy")),
                "spectral_participation": to_float(entry.get("spectral_participation")),
                "slow_modes_r50": to_int(entry.get("slow_modes_r50")),
                "slow_modes_r70": to_int(entry.get("slow_modes_r70")),
                "slow_modes_r90": to_int(entry.get("slow_modes_r90")),
            }

        run_scan_rows = [best_for_rung[k] for k in sorted(best_for_rung)]
        scan_rows.extend(run_scan_rows)

        core_rows = [r for r in run_scan_rows if to_int(r.get("k_rung")) is not None and r["k_rung"] >= 4]

        sigma = to_float(obj.get("sigma"))
        cyc_max = to_float(obj.get("cyc_max"))
        n_chiral = to_int(obj.get("n_chiral"))

        is_rev = bool(
            sigma is not None
            and cyc_max is not None
            and n_chiral is not None
            and sigma < 1e-8
            and cyc_max < 1e-8
            and n_chiral == 0
        )

        run_rows.append(
            {
                "exp_id": exp_id,
                "config_name": config_name,
                "n": n_val,
                "seed": seed,
                "tau": tau,
                "active_tau": active_tau,
                "log_file": log_file,
                "sigma": sigma,
                "sigma_u": to_float(obj.get("sigma_u")),
                "sigma_ratio": to_float(obj.get("sigma_ratio")),
                "frob_from_rank1": to_float(obj.get("frob_from_rank1")),
                "macro_gap": to_float(obj.get("macro_gap")),
                "cyc_max": cyc_max,
                "n_chiral": n_chiral,
                "n_absorb": to_int(obj.get("n_absorb")),
                "trans_ep": to_float(obj.get("trans_ep")),
                "n_trans": to_int(obj.get("n_trans")),
                "tilde_frob": median_or_none(r.get("frob") for r in core_rows),
                "tilde_sigma_pi": median_or_none(r.get("sigma_pi") for r in core_rows),
                "tilde_step_entropy": median_or_none(r.get("step_entropy") for r in core_rows),
                "tilde_pla2_gap": median_or_none(r.get("pla2_gap") for r in core_rows),
                "tilde_geo_r2": median_or_none(r.get("lagr_geo_r2") for r in core_rows),
                "tilde_diff_kl": median_or_none(r.get("lagr_diff_kl") for r in core_rows),
                "tilde_diff_alpha": median_or_none(r.get("lagr_diff_alpha") for r in core_rows),
                "k_points_core": len(core_rows),
                "is_REV": is_rev,
            }
        )

    scan_rows.sort(key=lambda r: (r["exp_id"], r["config_name"], r["n"], r["seed"], r["k_rung"]))
    run_rows.sort(key=lambda r: (r["exp_id"], r["config_name"], r["n"], r["seed"]))

    write_csv_gz(scan_out, scan_rows, SCAN_COLUMNS)
    write_csv_gz(run_out, run_rows, RUN_COLUMNS)

    counts_by_n = Counter(r["n"] for r in run_rows)
    counts_by_exp_id = Counter(r["exp_id"] for r in run_rows)

    per_exp_n_cfg = defaultdict(set)
    per_exp_n = defaultdict(list)
    for r in run_rows:
        key_cfg = (r["exp_id"], r["n"], r["config_name"])
        per_exp_n_cfg[key_cfg].add(r["seed"])
    for (exp_id, n_val, _cfg), seeds in per_exp_n_cfg.items():
        per_exp_n[(exp_id, n_val)].append(len(seeds))

    seed_summary_per_exp_n = {}
    for k in sorted(per_exp_n.keys()):
        exp_id, n_val = k
        seed_summary_per_exp_n[f"{exp_id}|n={n_val}"] = summarize_seed_counts(per_exp_n[k])

    seed_summary_per_exp_n_config = {}
    for k in sorted(per_exp_n_cfg.keys()):
        exp_id, n_val, cfg = k
        count = len(per_exp_n_cfg[k])
        seed_summary_per_exp_n_config[f"{exp_id}|n={n_val}|{cfg}"] = {
            "seed_count": count,
            "is_complete_10": count == 10,
        }

    scan_missingness = {}
    for col in [
        "frob",
        "sigma_pi",
        "step_entropy",
        "pla2_gap",
        "lagr_geo_r2",
        "lagr_diff_kl",
        "lagr_diff_alpha",
    ]:
        missing = 0
        for row in scan_rows:
            v = row.get(col)
            if v is None:
                missing += 1
        scan_missingness[col] = {
            "missing": missing,
            "total": len(scan_rows),
            "missing_rate": (missing / len(scan_rows)) if scan_rows else None,
        }

    dataset_expected_sum = 0
    for dataset_id in sorted(datasets.keys()):
        exp_runs = datasets[dataset_id].get("expected_runs")
        if isinstance(exp_runs, int):
            dataset_expected_sum += exp_runs

    report = {
        "manifest_path": str(manifest_path),
        "audits_path": str(audits_path),
        "manifest_dataset_ids_used": sorted(datasets.keys()),
        "manifest_expected_union_count_sum": dataset_expected_sum,
        "unique_runs_total": len(run_rows),
        "counts_by_n": {str(k): v for k, v in sorted(counts_by_n.items(), key=lambda x: x[0])},
        "counts_by_exp_id": dict(sorted(counts_by_exp_id.items())),
        "seeds_summary_per_exp_n": seed_summary_per_exp_n,
        "seeds_summary_per_exp_n_config": seed_summary_per_exp_n_config,
        "scan_missingness": scan_missingness,
        "scan_rung_table_columns": SCAN_COLUMNS,
        "run_summary_table_columns": RUN_COLUMNS,
        "n_values": sorted(counts_by_n.keys()),
        "wave1_inclusion_count": len(wave1_leaks),
        "git_commit": get_git_sha(),
    }

    with report_out.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)

    print(f"manifest_dataset_ids_used={report['manifest_dataset_ids_used']}")
    print(f"unique_runs_total={report['unique_runs_total']}")
    print(f"counts_by_n={report['counts_by_n']}")
    print(f"counts_by_exp_id={report['counts_by_exp_id']}")
    print(f"wrote={scan_out}")
    print(f"wrote={run_out}")
    print(f"wrote={report_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
