#!/usr/bin/env python3
"""Build T5 correlations/regression table assets from campaign_v3 union at anchor rung."""

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

try:
    from scipy.stats import spearmanr as scipy_spearmanr  # type: ignore

    SCIPY_AVAILABLE = True
except Exception:
    scipy_spearmanr = None
    SCIPY_AVAILABLE = False


COMPETITION_CONFIGS = ["A14_only", "A16_only", "A17_only", "A14_A17", "P4_row"]
METRICS = ["pla2_gap", "step_entropy", "lagr_geo_r2", "lagr_diff_kl"]
PAIRS = [
    ("pla2_gap", "step_entropy"),
    ("pla2_gap", "lagr_geo_r2"),
    ("pla2_gap", "lagr_diff_kl"),
    ("step_entropy", "lagr_geo_r2"),
    ("step_entropy", "lagr_diff_kl"),
    ("lagr_geo_r2", "lagr_diff_kl"),
]
CORRECTION_METHOD = "BH-FDR (per-n over 6 tests)"
METRIC_SYMBOL = {
    "pla2_gap": r"\mathrm{PLA2}",
    "step_entropy": r"H_{\mathrm{step}}",
    "lagr_geo_r2": r"R^2_{\mathrm{geo}}",
    "lagr_diff_kl": r"\mathrm{KL}^{\star}_{\mathrm{diff}}",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build T5 correlations/regression outputs.")
    parser.add_argument("--scan", default="paper/figdata/scan_rung_table.csv.gz")
    parser.add_argument("--run_summary", default="paper/figdata/run_summary_table.csv.gz")
    parser.add_argument("--out_tex", default="paper/tables/T5_correlations_regression.tex")
    parser.add_argument("--out_csv", default="paper/figdata/T5_correlations_regression.csv")
    parser.add_argument("--out_csv_gz", default="paper/figdata/T5_correlations_regression.csv.gz")
    parser.add_argument("--qa_out", default="paper/figdata/T5_QA.json")
    parser.add_argument("--exp", default="campaign_v3_union")
    parser.add_argument("--k", type=int, default=4)
    parser.add_argument("--perm", type=int, default=5000)
    parser.add_argument("--boot", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=12345)
    return parser.parse_args()


def fmt_num(v: float) -> str:
    if v is None or not math.isfinite(v):
        return "NA"
    return f"{v:.3g}"


def write_csv(path: Path, rows: List[dict], columns: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=columns)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in columns})


def write_csv_gz(path: Path, rows: List[dict], columns: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=columns)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in columns})


def rank_array(x: np.ndarray) -> np.ndarray:
    # Average-rank ties, deterministic.
    return pd.Series(x).rank(method="average").to_numpy(dtype=float)


def spearman_perm(x: np.ndarray, y: np.ndarray, b_perm: int, rng: np.random.Generator) -> Tuple[float, float]:
    rx = rank_array(x)
    ry = rank_array(y)
    if np.std(rx) == 0.0 or np.std(ry) == 0.0:
        return float("nan"), float("nan")
    rho_obs = float(np.corrcoef(rx, ry)[0, 1])
    abs_obs = abs(rho_obs)
    count = 0
    for _ in range(b_perm):
        ry_perm = rng.permutation(ry)
        rho_perm = float(np.corrcoef(rx, ry_perm)[0, 1])
        if abs(rho_perm) >= abs_obs:
            count += 1
    p = (count + 1) / (b_perm + 1)
    return rho_obs, float(p)


def bh_fdr_qvalues(pvals: List[float], m_tests: int = 6) -> List[float]:
    q = [float("nan")] * len(pvals)
    finite_idx = [i for i, p in enumerate(pvals) if p is not None and math.isfinite(p)]
    if not finite_idx:
        return q
    sorted_idx = sorted(finite_idx, key=lambda i: pvals[i])
    raw = {}
    for rank, idx in enumerate(sorted_idx, start=1):
        raw[idx] = min(1.0, float(pvals[idx]) * m_tests / rank)
    prev = 1.0
    for idx in reversed(sorted_idx):
        prev = min(prev, raw[idx])
        q[idx] = prev
    return q


def ols_beta1(y: np.ndarray, x: np.ndarray) -> float:
    if y.size == 0:
        return float("nan")
    x = x.astype(float)
    y = y.astype(float)
    xmat = np.column_stack([np.ones(y.size), x])
    beta = np.linalg.lstsq(xmat, y, rcond=None)[0]
    if beta.size < 2:
        return float("nan")
    return float(beta[1])


def bootstrap_beta1(y: np.ndarray, x: np.ndarray, b_boot: int, rng: np.random.Generator) -> Tuple[float, float]:
    n = y.size
    if n < 2:
        return float("nan"), float("nan")
    idx = rng.integers(0, n, size=(b_boot, n))
    vals = np.empty(b_boot, dtype=float)
    for i in range(b_boot):
        ys = y[idx[i]]
        xs = x[idx[i]]
        vals[i] = ols_beta1(ys, xs)
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return float(lo), float(hi)


def write_tex(
    path: Path,
    spearman_rows: List[dict],
    regression_rows: List[dict],
    n_values: List[int],
    k_rung: int,
    perm: int,
    boot: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    lines.append("% Auto-generated by paper/scripts/build_T5_correlations_regression.py")
    lines.append(r"\begin{table*}[t]")
    lines.append(r"\scriptsize")
    lines.append(r"\centering")
    lines.append(
        rf"\caption{{T5A: Spearman correlations among Lagrange probes at anchor rung $k={k_rung}$ (REV excluded), with BH-FDR correction per $n$ over 6 tests. p-values computed by SciPy or deterministic {perm}-permutation fallback.}}"
    )
    lines.append(r"\label{tab:T5A_correlations}")
    lines.append(r"\begin{tabular}{l l r r r r}")
    lines.append(r"\toprule")
    lines.append(r"$n$ & Pair & $\rho$ & $p$ & $q$ & $N$ \\")
    lines.append(r"\midrule")
    for i, n_val in enumerate(n_values):
        lines.append(rf"\multicolumn{{6}}{{l}}{{\textbf{{$n={n_val}$}}}} \\")
        for r in [x for x in spearman_rows if int(x["n"]) == n_val]:
            pair = rf"${METRIC_SYMBOL[r['x_metric']]}\leftrightarrow {METRIC_SYMBOL[r['y_metric']]}$"
            lines.append(
                f"{n_val} & {pair} & {fmt_num(r['rho'])} & {fmt_num(r['p_value'])} & {fmt_num(r['q_value'])} & {int(r['N_pair'])} \\\\"
            )
        if i != len(n_values) - 1:
            lines.append(r"\midrule")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table*}")
    lines.append("")
    lines.append(r"\begin{table}[t]")
    lines.append(r"\scriptsize")
    lines.append(r"\centering")
    lines.append(
        rf"\caption{{T5B: OLS regression by $n$ at $k={k_rung}$ (REV excluded): $\mathrm{{KL}}^{{\star}}_{{\mathrm{{diff}}}}(k{{=}}4)\sim 1 + \mathbb{{I}}[\mathrm{{competition}}]$. $\beta_1$ is competition$-$noncompetition. 95\% CI from bootstrap ($B={boot}$).}}"
    )
    lines.append(r"\label{tab:T5B_regression}")
    lines.append(r"\begin{tabular}{r r r r r r}")
    lines.append(r"\toprule")
    lines.append(r"$n$ & $\beta_1$ & 95\% CI & $N_{\mathrm{total}}$ & $N_{\mathrm{comp}}$ & $N_{\mathrm{noncomp}}$ \\")
    lines.append(r"\midrule")
    for r in regression_rows:
        ci = f"[{fmt_num(r['ci_low'])}, {fmt_num(r['ci_high'])}]"
        lines.append(
            f"{int(r['n'])} & {fmt_num(r['beta'])} & {ci} & {int(r['N_total'])} & {int(r['N_competition'])} & {int(r['N_noncompetition'])} \\\\"
        )
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    rng = np.random.default_rng(args.seed)

    scan = pd.read_csv(args.scan)
    run = pd.read_csv(args.run_summary)

    # Base filters and key join for REV.
    scan["k_rung"] = pd.to_numeric(scan["k_rung"], errors="coerce").astype("Int64")
    scan = scan[scan["k_rung"] == args.k].copy()
    scan["n"] = pd.to_numeric(scan["n"], errors="coerce").astype("Int64")
    scan["seed"] = pd.to_numeric(scan["seed"], errors="coerce").astype("Int64")
    scan = scan.dropna(subset=["n", "seed"]).copy()
    scan["n"] = scan["n"].astype(int)
    scan["seed"] = scan["seed"].astype(int)

    run["n"] = pd.to_numeric(run["n"], errors="coerce").astype("Int64")
    run["seed"] = pd.to_numeric(run["seed"], errors="coerce").astype("Int64")
    run = run.dropna(subset=["n", "seed"]).copy()
    run["n"] = run["n"].astype(int)
    run["seed"] = run["seed"].astype(int)
    run["is_REV_bool"] = run["is_REV"].map(
        lambda v: (str(v).strip().lower() in {"true", "t", "1", "yes", "y"}) if not isinstance(v, bool) else v
    )

    key_cols = ["exp_id", "config_name", "n", "seed"]
    run_key = run[key_cols + ["is_REV_bool"]].drop_duplicates(key_cols)
    merged = scan.merge(run_key, on=key_cols, how="left")
    if merged["is_REV_bool"].isna().any():
        missing = int(merged["is_REV_bool"].isna().sum())
        raise SystemExit(f"Failed REV join: {missing} scan rows missing run_summary is_REV mapping")

    n_values = sorted(int(x) for x in scan["n"].dropna().unique().tolist())
    qa_counts: Dict[str, dict] = {}
    for n_val in n_values:
        n0 = merged[merged["n"] == n_val]
        n1 = n0[n0["is_REV_bool"] == False]  # noqa: E712
        miss = {}
        for m in METRICS:
            col = pd.to_numeric(n1[m], errors="coerce")
            rate = float((~np.isfinite(col.to_numpy(dtype=float))).mean()) if len(col) > 0 else float("nan")
            miss[m] = rate
        qa_counts[str(n_val)] = {
            "rows_k4_before_rev_exclusion": int(len(n0)),
            "rows_k4_after_rev_exclusion": int(len(n1)),
            "missingness_rate_after_rev_exclusion": miss,
        }

    data = merged[merged["is_REV_bool"] == False].copy()  # noqa: E712
    data["is_competition"] = data["config_name"].isin(COMPETITION_CONFIGS).astype(int)

    found_comp = sorted(set(data["config_name"]).intersection(COMPETITION_CONFIGS))
    missing_comp = sorted(set(COMPETITION_CONFIGS) - set(found_comp))
    if len(found_comp) < 1:
        raise SystemExit("No competition configs found after filters; require at least one.")

    spearman_rows: List[dict] = []
    spearman_qa: Dict[str, dict] = {}
    # Correlations by n, with BH correction per n across 6 pairs.
    for n_val in n_values:
        n_df = data[data["n"] == n_val].copy()
        pvals: List[float] = []
        interim: List[dict] = []
        pair_ns: List[int] = []
        spearman_qa[str(n_val)] = {}
        for x_metric, y_metric in PAIRS:
            x = pd.to_numeric(n_df[x_metric], errors="coerce")
            y = pd.to_numeric(n_df[y_metric], errors="coerce")
            mask = np.isfinite(x.to_numpy(dtype=float)) & np.isfinite(y.to_numpy(dtype=float))
            x_arr = x.to_numpy(dtype=float)[mask]
            y_arr = y.to_numpy(dtype=float)[mask]
            n_pair = int(mask.sum())
            pair_ns.append(n_pair)

            if n_pair < 2:
                rho = float("nan")
                p_val = float("nan")
                p_method = "scipy" if SCIPY_AVAILABLE else f"perm_{args.perm}"
            else:
                if SCIPY_AVAILABLE and scipy_spearmanr is not None:
                    res = scipy_spearmanr(x_arr, y_arr)
                    rho = float(res.correlation) if res is not None else float("nan")
                    p_val = float(res.pvalue) if res is not None else float("nan")
                    p_method = "scipy"
                    if not math.isfinite(rho) or not math.isfinite(p_val):
                        rho, p_val = spearman_perm(x_arr, y_arr, args.perm, rng)
                        p_method = f"perm_{args.perm}"
                else:
                    rho, p_val = spearman_perm(x_arr, y_arr, args.perm, rng)
                    p_method = f"perm_{args.perm}"

            pvals.append(p_val)
            interim.append(
                {
                    "analysis_type": "spearman",
                    "exp_id": "campaign_v3_union",
                    "n": n_val,
                    "k_rung": args.k,
                    "x_metric": x_metric,
                    "y_metric": y_metric,
                    "rho": rho,
                    "p_value": p_val,
                    "N_pair": n_pair,
                    "p_method": p_method,
                    "correction_method": CORRECTION_METHOD,
                }
            )
            spearman_qa[str(n_val)][f"{x_metric}|{y_metric}"] = {
                "N_pair": n_pair,
                "p_method": p_method,
                "scipy_used": p_method == "scipy",
            }

        if max(pair_ns) < 50:
            raise SystemExit(f"Invariant failed for n={n_val}: all N_pair < 50 (max={max(pair_ns)}).")

        qvals = bh_fdr_qvalues(pvals, m_tests=6)
        for row, q in zip(interim, qvals):
            row["q_value"] = q
            spearman_rows.append(row)

    # Regression by n.
    regression_rows: List[dict] = []
    regression_qa: Dict[str, dict] = {}
    for n_val in n_values:
        n_df = data[data["n"] == n_val].copy()
        y = pd.to_numeric(n_df["lagr_diff_kl"], errors="coerce")
        x = pd.to_numeric(n_df["is_competition"], errors="coerce")
        mask = np.isfinite(y.to_numpy(dtype=float)) & np.isfinite(x.to_numpy(dtype=float))
        y_arr = y.to_numpy(dtype=float)[mask]
        x_arr = x.to_numpy(dtype=float)[mask]
        n_total = int(mask.sum())
        n_comp = int((x_arr == 1).sum())
        n_noncomp = int((x_arr == 0).sum())

        if n_total < 2:
            beta = float("nan")
            ci_low = float("nan")
            ci_high = float("nan")
        else:
            beta = ols_beta1(y_arr, x_arr)
            ci_low, ci_high = bootstrap_beta1(y_arr, x_arr, args.boot, rng)

        regression_rows.append(
            {
                "analysis_type": "regression",
                "exp_id": "campaign_v3_union",
                "n": n_val,
                "k_rung": args.k,
                "y_metric": "lagr_diff_kl",
                "x_term": "is_competition",
                "beta": beta,
                "ci_low": ci_low,
                "ci_high": ci_high,
                "N_total": n_total,
                "N_competition": n_comp,
                "N_noncompetition": n_noncomp,
                "bootstrap_B": args.boot,
            }
        )
        regression_qa[str(n_val)] = {
            "N_total": n_total,
            "N_competition": n_comp,
            "N_noncompetition": n_noncomp,
        }

    # Combine outputs.
    all_rows = spearman_rows + regression_rows
    columns = [
        "analysis_type",
        "exp_id",
        "n",
        "k_rung",
        "x_metric",
        "y_metric",
        "rho",
        "p_value",
        "q_value",
        "N_pair",
        "p_method",
        "correction_method",
        "x_term",
        "beta",
        "ci_low",
        "ci_high",
        "N_total",
        "N_competition",
        "N_noncompetition",
        "bootstrap_B",
    ]

    # Strict row count checks.
    n_spear = sum(1 for r in all_rows if r["analysis_type"] == "spearman")
    n_reg = sum(1 for r in all_rows if r["analysis_type"] == "regression")
    expected_spearman = len(n_values) * len(PAIRS)
    expected_reg = len(n_values)
    if n_spear != expected_spearman:
        raise SystemExit(f"Expected {expected_spearman} spearman rows, got {n_spear}")
    if n_reg != expected_reg:
        raise SystemExit(f"Expected {expected_reg} regression rows, got {n_reg}")

    out_csv = Path(args.out_csv)
    out_csv_gz = Path(args.out_csv_gz)
    out_tex = Path(args.out_tex)
    qa_out = Path(args.qa_out)

    write_csv(out_csv, all_rows, columns)
    write_csv_gz(out_csv_gz, all_rows, columns)
    write_tex(out_tex, spearman_rows, regression_rows, n_values, args.k, args.perm, args.boot)

    qa = {
        "exp_id": "campaign_v3_union",
        "k_rung": args.k,
        "scipy_available": SCIPY_AVAILABLE,
        "correction_method": CORRECTION_METHOD,
        "competition_configs": {
            "defined": COMPETITION_CONFIGS,
            "found": found_comp,
            "missing": missing_comp,
        },
        "counts_per_n": qa_counts,
        "correlation": spearman_qa,
        "regression": regression_qa,
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
