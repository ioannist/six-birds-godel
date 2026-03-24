#!/usr/bin/env python3
"""Build T3 headline metrics summary table + CSV outputs."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


CONFIG_ORDER = [
    "empty",
    "baseline",
    "full_action",
    "full_all",
    "gen6_core_A12_A25",
]
N_ORDER = [32, 64, 128, 256]
METRICS = [
    "tilde_frob",
    "tilde_sigma_pi",
    "tilde_geo_r2",
    "tilde_pla2_gap",
    "tilde_diff_kl",
]
METRIC_LABELS_TEX = {
    "tilde_frob": r"$\widetilde{\mathrm{frob}}$",
    "tilde_sigma_pi": r"$\widetilde{\Sigma}_{10}(\pi)$",
    "tilde_geo_r2": r"$\widetilde{R^2_{\mathrm{geo}}}$",
    "tilde_pla2_gap": r"$\widetilde{\mathrm{PLA2}}$",
    "tilde_diff_kl": r"$\widetilde{\mathrm{KL}^{\star}_{\mathrm{diff}}}$",
}
EPS = 1e-15


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build T3 headline metrics table.")
    parser.add_argument("--run_summary", default="paper/figdata/run_summary_table.csv.gz")
    parser.add_argument("--t2b", default="paper/figdata/T2B_key_conditions.csv.gz")
    parser.add_argument("--out_tex", default="paper/tables/T3_headline_metrics.tex")
    parser.add_argument("--out_csv", default="paper/figdata/T3_headline_metrics.csv")
    parser.add_argument("--out_csv_gz", default="paper/figdata/T3_headline_metrics.csv.gz")
    parser.add_argument("--qa_out", default="paper/figdata/T3_QA.json")
    parser.add_argument("--exp", default="campaign_v3_union")
    parser.add_argument("--bootstrap", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=12345)
    return parser.parse_args()


def fmt_num(v: float) -> str:
    if v is None or not math.isfinite(v):
        return "NA"
    # Use compact formatting suitable for dense table cells.
    return f"{v:.3g}"


def write_csv(path: Path, rows: List[dict], columns: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=columns)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in columns})


def write_csv_gz(path: Path, rows: List[dict], columns: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=columns)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in columns})


def to_float_array(values: pd.Series) -> np.ndarray:
    arr = pd.to_numeric(values, errors="coerce").to_numpy(dtype=float)
    return arr[np.isfinite(arr)]


def median_and_ci(values: np.ndarray, bootstrap: int, rng: np.random.Generator) -> Tuple[float, float, float]:
    n = int(values.size)
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    med = float(np.median(values))
    if n < 2:
        return med, float("nan"), float("nan")
    idx = rng.integers(0, n, size=(bootstrap, n))
    med_boot = np.median(values[idx], axis=1)
    lo, hi = np.percentile(med_boot, [2.5, 97.5])
    return med, float(lo), float(hi)


def delta_paired_or_unpaired(
    cfg_seed_to_val: Dict[int, float],
    base_seed_to_val: Dict[int, float],
    cfg_vals: np.ndarray,
    base_vals: np.ndarray,
    bootstrap: int,
    rng: np.random.Generator,
) -> Tuple[float, float, float, str]:
    common = sorted(set(cfg_seed_to_val.keys()) & set(base_seed_to_val.keys()))
    if len(common) >= 2:
        diffs = np.array([cfg_seed_to_val[s] - base_seed_to_val[s] for s in common], dtype=float)
        med = float(np.median(diffs))
        idx = rng.integers(0, diffs.size, size=(bootstrap, diffs.size))
        med_boot = np.median(diffs[idx], axis=1)
        lo, hi = np.percentile(med_boot, [2.5, 97.5])
        return med, float(lo), float(hi), "paired"

    # Fallback: unpaired bootstrap.
    if cfg_vals.size == 0 or base_vals.size == 0:
        return float("nan"), float("nan"), float("nan"), "unpaired"
    med = float(np.median(cfg_vals) - np.median(base_vals))
    if cfg_vals.size < 2 or base_vals.size < 2:
        return med, float("nan"), float("nan"), "unpaired"
    idx_cfg = rng.integers(0, cfg_vals.size, size=(bootstrap, cfg_vals.size))
    idx_base = rng.integers(0, base_vals.size, size=(bootstrap, base_vals.size))
    med_boot = np.median(cfg_vals[idx_cfg], axis=1) - np.median(base_vals[idx_base], axis=1)
    lo, hi = np.percentile(med_boot, [2.5, 97.5])
    return med, float(lo), float(hi), "unpaired"


def mad(values: np.ndarray) -> float:
    if values.size == 0:
        return float("nan")
    med = float(np.median(values))
    return float(np.median(np.abs(values - med)))


def es_mad(cfg_vals: np.ndarray, base_vals: np.ndarray) -> float:
    if cfg_vals.size == 0 or base_vals.size == 0:
        return float("nan")
    med_cfg = float(np.median(cfg_vals))
    med_base = float(np.median(base_vals))
    den = 0.5 * (mad(cfg_vals) + mad(base_vals)) + EPS
    return float((med_cfg - med_base) / den)


def make_metric_cell(r: dict, is_baseline: bool) -> str:
    line1 = f"{fmt_num(r['median'])} [{fmt_num(r['ci_low'])}, {fmt_num(r['ci_high'])}]"
    if is_baseline:
        line2 = r"\scriptsize baseline"
    else:
        line2 = (
            r"\scriptsize "
            + r"$\Delta$ "
            + f"{fmt_num(r['delta_vs_baseline_median'])} [{fmt_num(r['delta_ci_low'])}, {fmt_num(r['delta_ci_high'])}]"
            + f"; ES {fmt_num(r['es_mad_vs_baseline'])}"
        )
    return r"\shortstack[l]{" + line1 + r"\\ " + line2 + "}"


def write_tex(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    lines.append("% Auto-generated by paper/scripts/build_T3_headline_metrics.py")
    lines.append(r"\begin{table*}[t]")
    lines.append(r"\scriptsize")
    lines.append(r"\centering")
    lines.append(
        r"\caption{Headline metrics by condition and micro size, using medians over core rungs ($k\geq 4$). Entries report median with bootstrap 95\% CI ($B=5000$), plus $\Delta$ vs baseline and robust $ES_{\mathrm{MAD}}$. NA indicates the condition is not present in the n=256 selective suite.}"
    )
    lines.append(r"\label{tab:T3_headline_metrics}")
    lines.append(r"\begin{tabular}{l r p{0.145\linewidth} p{0.145\linewidth} p{0.145\linewidth} p{0.145\linewidth} p{0.145\linewidth}}")
    lines.append(r"\toprule")
    lines.append(
        r"Condition & $|E|$ & "
        + " & ".join(METRIC_LABELS_TEX[m] for m in METRICS)
        + r" \\"
    )
    lines.append(r"\midrule")

    rows_df = pd.DataFrame(rows)
    for n_val in N_ORDER:
        lines.append(rf"\multicolumn{{7}}{{l}}{{\textbf{{$n={n_val}$}}}} \\")
        for cfg in CONFIG_ORDER:
            sub = rows_df[(rows_df["n"] == n_val) & (rows_df["config_name"] == cfg)].copy()
            if sub.empty:
                continue
            sub = sub.set_index("metric")
            short_label = str(sub.iloc[0]["short_label"])
            e_count = int(sub.iloc[0]["E_enabled_count"])
            cells = [make_metric_cell(sub.loc[m].to_dict(), cfg == "baseline") for m in METRICS]
            cfg_tex = cfg.replace("_", r"\_")
            lines.append(
                f"{short_label} ({cfg_tex}) & {e_count} & " + " & ".join(cells) + r" \\"
            )
        if n_val != N_ORDER[-1]:
            lines.append(r"\midrule")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table*}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    rng = np.random.default_rng(args.seed)

    run_df = pd.read_csv(args.run_summary)
    run_df["n"] = pd.to_numeric(run_df["n"], errors="coerce").astype("Int64")
    run_df["seed"] = pd.to_numeric(run_df["seed"], errors="coerce").astype("Int64")
    run_df = run_df.dropna(subset=["n", "seed"]).copy()
    run_df["n"] = run_df["n"].astype(int)
    run_df["seed"] = run_df["seed"].astype(int)

    # Keep only requested n/configs.
    run_df = run_df[run_df["n"].isin(N_ORDER)].copy()

    t2b = pd.read_csv(args.t2b)
    t2b = t2b[t2b["config_name"].isin(CONFIG_ORDER)].copy()
    if t2b["config_name"].nunique() != len(CONFIG_ORDER):
        found = sorted(t2b["config_name"].dropna().unique().tolist())
        missing = [c for c in CONFIG_ORDER if c not in found]
        raise SystemExit(f"Missing required configs in T2B: {missing}")
    meta = t2b.set_index("config_name")[["short_label", "E_enabled_count"]].to_dict("index")

    # Coverage check in QA: every (n, config) should have 10 seeds.
    seed_counts = (
        run_df[run_df["config_name"].isin(CONFIG_ORDER)]
        .groupby(["n", "config_name"])["seed"]
        .nunique()
        .to_dict()
    )
    bad_seed_counts = []
    for n_val in N_ORDER:
        for cfg in CONFIG_ORDER:
            count = int(seed_counts.get((n_val, cfg), 0))
            if count != 10:
                bad_seed_counts.append({"n": n_val, "config_name": cfg, "seed_count": count})

    rows: List[dict] = []
    qa_n_eff: Dict[str, Dict[str, Dict[str, int]]] = {str(n): {} for n in N_ORDER}
    qa_delta_method: Dict[str, Dict[str, Dict[str, str]]] = {str(n): {} for n in N_ORDER}
    qa_n_eff_lt10: List[dict] = []

    for n_val in N_ORDER:
        n_df = run_df[(run_df["n"] == n_val) & (run_df["config_name"].isin(CONFIG_ORDER))].copy()
        qa_n_eff[str(n_val)] = {cfg: {} for cfg in CONFIG_ORDER}
        qa_delta_method[str(n_val)] = {cfg: {} for cfg in CONFIG_ORDER}

        for metric in METRICS:
            # Prepare baseline arrays/maps once per metric,n.
            base_df = n_df[n_df["config_name"] == "baseline"][["seed", metric]].copy()
            base_df[metric] = pd.to_numeric(base_df[metric], errors="coerce")
            base_df = base_df[np.isfinite(base_df[metric])].copy()
            base_vals = base_df[metric].to_numpy(dtype=float)
            base_seed_map = {int(r.seed): float(getattr(r, metric)) for r in base_df.itertuples(index=False)}

            for cfg in CONFIG_ORDER:
                sub = n_df[n_df["config_name"] == cfg][["seed", metric]].copy()
                sub[metric] = pd.to_numeric(sub[metric], errors="coerce")
                sub = sub[np.isfinite(sub[metric])].copy()
                vals = sub[metric].to_numpy(dtype=float)
                seed_map = {int(r.seed): float(getattr(r, metric)) for r in sub.itertuples(index=False)}

                med, ci_lo, ci_hi = median_and_ci(vals, args.bootstrap, rng)
                n_eff = int(vals.size)
                qa_n_eff[str(n_val)][cfg][metric] = n_eff
                if n_eff < 10:
                    qa_n_eff_lt10.append(
                        {"n": n_val, "config_name": cfg, "metric": metric, "n_eff": n_eff}
                    )

                if cfg == "baseline":
                    d_med, d_lo, d_hi, d_method = 0.0, 0.0, 0.0, "self"
                    es = 0.0
                else:
                    d_med, d_lo, d_hi, d_method = delta_paired_or_unpaired(
                        seed_map,
                        base_seed_map,
                        vals,
                        base_vals,
                        args.bootstrap,
                        rng,
                    )
                    es = es_mad(vals, base_vals)
                qa_delta_method[str(n_val)][cfg][metric] = d_method

                rows.append(
                    {
                        "exp_id": "campaign_v3_union",
                        "n": n_val,
                        "config_name": cfg,
                        "short_label": meta[cfg]["short_label"],
                        "E_enabled_count": int(meta[cfg]["E_enabled_count"]),
                        "metric": metric,
                        "n_eff": n_eff,
                        "median": med,
                        "ci_low": ci_lo,
                        "ci_high": ci_hi,
                        "delta_vs_baseline_median": d_med,
                        "delta_ci_low": d_lo,
                        "delta_ci_high": d_hi,
                        "delta_method": d_method,
                        "es_mad_vs_baseline": es,
                    }
                )

    # Deterministic sort and strict row count.
    cfg_rank = {c: i for i, c in enumerate(CONFIG_ORDER)}
    metric_rank = {m: i for i, m in enumerate(METRICS)}
    rows = sorted(rows, key=lambda r: (r["n"], cfg_rank[r["config_name"]], metric_rank[r["metric"]]))
    expected_rows = len(N_ORDER) * len(CONFIG_ORDER) * len(METRICS)
    if len(rows) != expected_rows:
        raise SystemExit(f"Expected {expected_rows} rows, got {len(rows)}")

    columns = [
        "exp_id",
        "n",
        "config_name",
        "short_label",
        "E_enabled_count",
        "metric",
        "n_eff",
        "median",
        "ci_low",
        "ci_high",
        "delta_vs_baseline_median",
        "delta_ci_low",
        "delta_ci_high",
        "delta_method",
        "es_mad_vs_baseline",
    ]

    out_csv = Path(args.out_csv)
    out_csv_gz = Path(args.out_csv_gz)
    out_tex = Path(args.out_tex)
    qa_out = Path(args.qa_out)

    write_csv(out_csv, rows, columns)
    write_csv_gz(out_csv_gz, rows, columns)
    write_tex(out_tex, rows)

    qa = {
        "exp_id": "campaign_v3_union",
        "bootstrap": args.bootstrap,
        "seed": args.seed,
        "configs": CONFIG_ORDER,
        "metrics": METRICS,
        "seed_count_check_per_(n,config)": {
            f"{n}|{cfg}": int(seed_counts.get((n, cfg), 0))
            for n in N_ORDER
            for cfg in CONFIG_ORDER
        },
        "seed_count_violations": bad_seed_counts,
        "n_eff": qa_n_eff,
        "delta_method": qa_delta_method,
        "n_eff_lt10": qa_n_eff_lt10,
    }
    qa_out.parent.mkdir(parents=True, exist_ok=True)
    qa_out.write_text(json.dumps(qa, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"wrote={out_tex}")
    print(f"wrote={out_csv}")
    print(f"wrote={out_csv_gz}")
    print(f"wrote={qa_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
