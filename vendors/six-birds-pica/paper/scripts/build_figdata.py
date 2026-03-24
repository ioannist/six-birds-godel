#!/usr/bin/env python3
"""Build paper-facing figdata tables from KEY_AUDIT_JSON logs."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import os
import re
import statistics
import subprocess
import sys
from glob import glob
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

sys.path.append(str(Path(__file__).resolve().parent))
from plot_common import map_to_nearest_rung, rungs_for_n


TOKEN = "KEY_AUDIT_JSON"


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
    parser = argparse.ArgumentParser(description="Build paper figdata tables from audit logs.")
    parser.add_argument("--exp", default="EXP-112", help="Experiment id to extract (default: EXP-112).")
    parser.add_argument(
        "--log_glob",
        default="lab/runs/campaign_v3/wave_3/wave_3/*.log",
        help="Glob for log files (default: wave_3 logs).",
    )
    parser.add_argument("--outdir", default="paper/figdata", help="Output directory.")
    parser.add_argument("--format", default="csv.gz", help="Output format (only csv.gz supported).")
    parser.add_argument("--force", action="store_true", help="Overwrite outputs if present.")
    return parser.parse_args()


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
    clean: List[float] = [v for v in values if v is not None and math.isfinite(v)]
    if not clean:
        return None
    return float(statistics.median(clean))


def get_step_rank(obj: Dict[str, object]) -> float:
    step = to_float(obj.get("step"))
    if step is not None:
        return step
    t_val = to_float(obj.get("t"))
    if t_val is not None:
        return t_val
    return float("-inf")


def extract_key_audit_jsons(text: str) -> List[Tuple[Dict[str, object], int]]:
    """Extract KEY_AUDIT_JSON payloads, robust to multiline JSON objects."""
    out: List[Tuple[Dict[str, object], int]] = []
    i = 0
    n = len(text)

    while i < n:
        idx = text.find(TOKEN, i)
        if idx < 0:
            break
        j = idx + len(TOKEN)

        while j < n and text[j] != "{":
            j += 1
        if j >= n:
            break

        start = j
        depth = 0
        in_string = False
        escaped = False
        end = None

        for pos in range(start, n):
            ch = text[pos]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue

            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = pos + 1
                    break

        if end is None:
            break

        snippet = text[start:end]
        try:
            obj = json.loads(snippet)
            if isinstance(obj, dict):
                out.append((obj, start))
        except json.JSONDecodeError:
            pass

        i = end

    return out


def parse_filename(path: str) -> Tuple[Optional[str], Optional[int], Optional[int], Optional[str]]:
    base = os.path.basename(path)
    m = re.match(r"^(EXP-[^_]+)_s(\d+)_n(\d+)_(.+)\.log$", base)
    if not m:
        return None, None, None, None
    exp_id = m.group(1)
    seed = int(m.group(2))
    n = int(m.group(3))
    config_name = m.group(4)
    return exp_id, seed, n, config_name


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


def main() -> int:
    args = parse_args()
    if args.format != "csv.gz":
        raise SystemExit(f"Unsupported --format {args.format!r}. Only 'csv.gz' is supported.")

    log_paths = sorted(glob(args.log_glob))
    if not log_paths:
        raise SystemExit(f"No log files matched: {args.log_glob}")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    scan_out = outdir / "scan_rung_table.csv.gz"
    run_out = outdir / "run_summary_table.csv.gz"
    report_out = outdir / "figdata_build_report.json"

    if not args.force:
        for p in (scan_out, run_out, report_out):
            if p.exists():
                raise SystemExit(f"Output exists: {p} (use --force to overwrite)")

    audit_records_extracted_total = 0
    logs_without_audit_json = 0
    logs_exp_mismatch = 0
    logs_bad_identity = 0

    # run_id -> selected record
    selected: Dict[Tuple[str, str, int, int], Dict[str, object]] = {}

    for path in log_paths:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()

        payloads = extract_key_audit_jsons(text)
        if not payloads:
            logs_without_audit_json += 1
            continue

        audit_records_extracted_total += len(payloads)
        best_obj, _ = max(payloads, key=lambda x: (get_step_rank(x[0]), x[1]))

        exp_file, seed_file, n_file, cfg_file = parse_filename(path)
        exp_id = best_obj.get("exp_id")
        if not isinstance(exp_id, str):
            exp_id = exp_file
        if exp_id != args.exp:
            logs_exp_mismatch += 1
            continue

        config_name = best_obj.get("config_name")
        if not isinstance(config_name, str):
            config_name = cfg_file

        seed = to_int(best_obj.get("seed"))
        if seed is None:
            seed = seed_file

        n_val = to_int(best_obj.get("n"))
        if n_val is None:
            n_val = n_file

        if not isinstance(config_name, str) or seed is None or n_val is None:
            logs_bad_identity += 1
            continue

        run_id = (exp_id, config_name, int(n_val), int(seed))
        cand = {
            "obj": best_obj,
            "log_file": os.path.basename(path),
            "rank": (get_step_rank(best_obj), os.path.basename(path)),
        }
        prev = selected.get(run_id)
        if prev is None or cand["rank"] > prev["rank"]:
            selected[run_id] = cand

    unique_runs_total = len(selected)
    if args.exp == "EXP-112" and unique_runs_total != 2070:
        raise SystemExit(
            f"ERROR: expected 2070 unique runs for EXP-112, got {unique_runs_total}."
        )

    scan_rows: List[Dict[str, object]] = []
    run_rows: List[Dict[str, object]] = []

    for run_id, rec in selected.items():
        exp_id, config_name, n_val, seed = run_id
        obj = rec["obj"]
        log_file = rec["log_file"]
        tau = to_int(obj.get("tau"))
        active_tau = to_int(obj.get("active_tau"))

        rungs = rungs_for_n(n_val)
        scan_entries = obj.get("multi_scale_scan")
        if not isinstance(scan_entries, list):
            scan_entries = []

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
            # Deterministic tie-breaker on equal distance: smaller k_eff.
            rank = (logdist, k_eff)
            prev_rank = best_rank_for_rung.get(rung)
            if prev_rank is not None and rank >= prev_rank:
                continue
            best_rank_for_rung[rung] = rank

            row = {
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
            best_for_rung[rung] = row

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

        run_row = {
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
        run_rows.append(run_row)

    scan_rows.sort(key=lambda r: (r["config_name"], r["n"], r["seed"], r["k_rung"]))
    run_rows.sort(key=lambda r: (r["config_name"], r["n"], r["seed"]))

    write_csv_gz(scan_out, scan_rows, SCAN_COLUMNS)
    write_csv_gz(run_out, run_rows, RUN_COLUMNS)

    unique_configs = sorted({r[1] for r in selected})
    n_values = sorted({r[2] for r in selected})
    seeds_by_pair: Dict[Tuple[str, int], set] = {}
    for (_, config_name, n_val, seed) in selected:
        key = (config_name, n_val)
        seeds_by_pair.setdefault(key, set()).add(seed)
    seed_counts = sorted(len(v) for v in seeds_by_pair.values())
    seed_count_summary = {
        "pairs_total": len(seed_counts),
        "min": min(seed_counts) if seed_counts else None,
        "median": statistics.median(seed_counts) if seed_counts else None,
        "max": max(seed_counts) if seed_counts else None,
    }

    report = {
        "exp_id": args.exp,
        "log_files_scanned": len(log_paths),
        "audit_records_extracted_total": audit_records_extracted_total,
        "unique_runs_total": unique_runs_total,
        "unique_configs": len(unique_configs),
        "n_values": n_values,
        "seeds_per_config_n": seed_count_summary,
        "scan_rung_table_columns": SCAN_COLUMNS,
        "run_summary_table_columns": RUN_COLUMNS,
        "git_commit": get_git_sha(),
        "anomalies": {
            "logs_without_audit_json": logs_without_audit_json,
            "logs_exp_mismatch": logs_exp_mismatch,
            "logs_bad_identity": logs_bad_identity,
        },
    }
    with open(report_out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)

    print(f"log_files_scanned={len(log_paths)}")
    print(f"audit_records_extracted_total={audit_records_extracted_total}")
    print(f"unique_runs_total={unique_runs_total}")
    print(f"unique_configs={len(unique_configs)}")
    print(f"n_values={n_values}")
    print(f"seed_count_summary={seed_count_summary}")
    print(f"wrote={scan_out}")
    print(f"wrote={run_out}")
    print(f"wrote={report_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
