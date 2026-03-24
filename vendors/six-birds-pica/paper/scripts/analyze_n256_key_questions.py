#!/usr/bin/env python3
"""n=256 key-question diagnostic analysis pack (N3)."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Analyze n=256 key questions and emit diagnostics.")
    p.add_argument("--run_summary", default="paper/figdata/run_summary_table.csv.gz")
    p.add_argument("--scan", default="paper/figdata/scan_rung_table.csv.gz")
    p.add_argument("--manifest", default="paper/figdata/paper_dataset_manifest.json")
    p.add_argument("--out_csv", default="paper/figdata/N3_n256_key_questions.csv.gz")
    p.add_argument("--outdir_fig", default="paper/fig")
    p.add_argument("--out_memo", default="paper/figdata/N3_decision_memo.md")
    p.add_argument("--qa_out", default="paper/figdata/N3_QA.json")
    p.add_argument("--bootstrap", type=int, default=5000)
    p.add_argument("--perm", type=int, default=5000)
    p.add_argument("--seed", type=int, default=12345)
    return p.parse_args()


def to_bool_series(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s
    lower = s.astype(str).str.strip().str.lower()
    mapped = lower.map({"true": True, "false": False, "1": True, "0": False})
    return mapped.fillna(False).astype(bool)


def finite_array(values: Iterable[object]) -> np.ndarray:
    out = pd.to_numeric(pd.Series(list(values)), errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    return out.to_numpy(dtype=float)


def log10p1_nonneg(values: Iterable[object]) -> np.ndarray:
    arr = finite_array(values)
    if arr.size == 0:
        return arr
    return np.log10(1.0 + np.maximum(arr, 0.0))


def bootstrap_median_ci(values: np.ndarray, B: int, rng: np.random.Generator) -> Tuple[float, float, float]:
    if values.size == 0:
        return (math.nan, math.nan, math.nan)
    med = float(np.median(values))
    if values.size == 1:
        return (med, med, med)
    idx = rng.integers(0, values.size, size=(B, values.size))
    meds = np.median(values[idx], axis=1)
    lo, hi = np.percentile(meds, [2.5, 97.5])
    return (med, float(lo), float(hi))


def bootstrap_delta_ci(a: np.ndarray, b: np.ndarray, B: int, rng: np.random.Generator) -> Tuple[float, float, float]:
    if a.size == 0 or b.size == 0:
        return (math.nan, math.nan, math.nan)
    obs = float(np.median(a) - np.median(b))
    if a.size == 1 and b.size == 1:
        return (obs, obs, obs)
    ia = rng.integers(0, a.size, size=(B, a.size))
    ib = rng.integers(0, b.size, size=(B, b.size))
    ds = np.median(a[ia], axis=1) - np.median(b[ib], axis=1)
    lo, hi = np.percentile(ds, [2.5, 97.5])
    return (obs, float(lo), float(hi))


def es_mad(a: np.ndarray, b: np.ndarray, eps: float = 1e-15) -> float:
    if a.size == 0 or b.size == 0:
        return math.nan
    ma = float(np.median(a))
    mb = float(np.median(b))
    mada = float(np.median(np.abs(a - ma)))
    madb = float(np.median(np.abs(b - mb)))
    den = 0.5 * (mada + madb) + eps
    return (ma - mb) / den


def wilson_ci(k: int, n: int, z: float = 1.959963984540054) -> Tuple[float, float, float]:
    if n <= 0:
        return (math.nan, math.nan, math.nan)
    p = k / n
    den = 1.0 + (z * z) / n
    center = (p + (z * z) / (2.0 * n)) / den
    half = z * math.sqrt((p * (1.0 - p) + (z * z) / (4.0 * n)) / n) / den
    return (p, max(0.0, center - half), min(1.0, center + half))


def _pearson(x: np.ndarray, y: np.ndarray) -> float:
    x0 = x - x.mean()
    y0 = y - y.mean()
    den = np.sqrt(np.sum(x0 * x0) * np.sum(y0 * y0))
    if den <= 0.0:
        return math.nan
    return float(np.sum(x0 * y0) / den)


def spearman_rho(x: np.ndarray, y: np.ndarray) -> float:
    if x.size != y.size or x.size < 2:
        return math.nan
    rx = pd.Series(x).rank(method="average").to_numpy(dtype=float)
    ry = pd.Series(y).rank(method="average").to_numpy(dtype=float)
    return _pearson(rx, ry)


def spearman_perm_pvalue(x: np.ndarray, y: np.ndarray, B: int, rng: np.random.Generator) -> Tuple[float, float]:
    rho = spearman_rho(x, y)
    if not math.isfinite(rho):
        return (math.nan, math.nan)
    count = 0
    for _ in range(B):
        yp = rng.permutation(y)
        rp = spearman_rho(x, yp)
        if math.isfinite(rp) and abs(rp) >= abs(rho):
            count += 1
    p = (count + 1) / (B + 1)
    return (rho, p)


def parse_key_audit_jsons(text: str) -> List[Dict[str, object]]:
    token = "KEY_AUDIT_JSON"
    out: List[Dict[str, object]] = []
    i = 0
    n = len(text)
    while i < n:
        j = text.find(token, i)
        if j < 0:
            break
        k = j + len(token)
        while k < n and text[k] != "{":
            k += 1
        if k >= n:
            break
        start = k
        depth = 0
        in_str = False
        esc = False
        end = None
        for pos in range(start, n):
            ch = text[pos]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
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
                out.append(obj)
        except json.JSONDecodeError:
            pass
        i = end
    return out


def _rank_value(obj: Dict[str, object]) -> Tuple[float, float]:
    step = pd.to_numeric(pd.Series([obj.get("step")]), errors="coerce").iloc[0]
    tval = pd.to_numeric(pd.Series([obj.get("t")]), errors="coerce").iloc[0]
    s = float(step) if pd.notna(step) else float("-inf")
    t = float(tval) if pd.notna(tval) else float("-inf")
    return (s, t)


def load_enabled_from_log(log_path: str) -> Tuple[Optional[List[str]], Optional[str]]:
    p = Path(log_path)
    if not p.exists():
        return (None, None)
    text = p.read_text(encoding="utf-8", errors="replace")
    recs = parse_key_audit_jsons(text)
    if not recs:
        return (None, None)
    best = max(recs, key=_rank_value)
    pica_cfg = best.get("pica_config")
    if not isinstance(pica_cfg, dict):
        return (None, None)
    enabled = pica_cfg.get("enabled")
    if not isinstance(enabled, list):
        return (None, None)
    cells = []
    bits = []
    for i, row in enumerate(enabled):
        if not isinstance(row, list):
            return (None, None)
        for j, val in enumerate(row):
            on = bool(val)
            bits.append("1" if on else "0")
            if on:
                cells.append(f"P{i+1}<-P{j+1}")
    cells = sorted(cells)
    fp = hashlib.sha256("".join(bits).encode("utf-8")).hexdigest()[:16]
    return (cells, fp)


def jittered_scatter(ax, x: float, yvals: np.ndarray, rng: np.random.Generator) -> None:
    if yvals.size == 0:
        return
    jitter = rng.uniform(-0.12, 0.12, size=yvals.size)
    ax.scatter(np.full(yvals.size, x) + jitter, yvals, s=12, alpha=0.65)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def main() -> int:
    args = parse_args()
    seed = int(args.seed)
    B = int(args.bootstrap)
    P = int(args.perm)
    base_rng = np.random.default_rng(seed)

    run = pd.read_csv(args.run_summary)
    scan = pd.read_csv(args.scan)
    with open(args.manifest, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)

    run["is_REV"] = to_bool_series(run["is_REV"])
    for c in ["n", "seed", "tau", "active_tau", "k_points_core"]:
        if c in run.columns:
            run[c] = pd.to_numeric(run[c], errors="coerce")
    for c in ["n", "seed", "k_rung"]:
        if c in scan.columns:
            scan[c] = pd.to_numeric(scan[c], errors="coerce")

    rev_map = run[["exp_id", "config_name", "n", "seed", "is_REV"]].drop_duplicates()
    scan = scan.merge(rev_map, on=["exp_id", "config_name", "n", "seed"], how="left")
    scan["is_REV"] = scan["is_REV"].fillna(False).astype(bool)

    rows: List[Dict[str, object]] = []
    qa: Dict[str, object] = {
        "seed": seed,
        "bootstrap": B,
        "perm": P,
        "manifest_path": args.manifest,
        "wave2_truncation_count": manifest.get("notes", {}).get("wave2_truncation_count"),
    }

    def add_row(
        *,
        question_id: str,
        analysis_id: str,
        n: int,
        group_A: str,
        group_B: str,
        metric: str,
        A: np.ndarray,
        Bvals: np.ndarray,
        data_scope: str,
        support_note: str,
        rng: np.random.Generator,
    ) -> None:
        medA = float(np.median(A)) if A.size else math.nan
        medB = float(np.median(Bvals)) if Bvals.size else math.nan
        dmed, lo, hi = bootstrap_delta_ci(A, Bvals, B, rng)
        rows.append(
            {
                "question_id": question_id,
                "analysis_id": analysis_id,
                "n": n,
                "group_A": group_A,
                "group_B": group_B,
                "metric": metric,
                "N_A": int(A.size),
                "N_B": int(Bvals.size),
                "median_A": medA,
                "median_B": medB,
                "delta_median": dmed,
                "ci_low": lo,
                "ci_high": hi,
                "ES_MAD": es_mad(A, Bvals),
                "support_note": support_note,
                "data_scope": data_scope,
            }
        )

    # Q1: partition competition survival
    q1_scope = "ds_exp112_wave2_n256_selective_unique + ds_exp107_wave2_n256_sweep"
    q1_cfgs = ["A14_only", "A16_only", "A17_only"]
    q1_ctrls = ["baseline", "full_action"]
    q1_df = scan[(scan["n"] == 256) & (scan["k_rung"] == 4) & (~scan["is_REV"])].copy()
    q1_metrics = [("lagr_diff_kl", "lagr_diff_kl_k4"), ("lagr_geo_r2", "lagr_geo_r2_k4")]
    q1_n_by_cfg = q1_df["config_name"].value_counts().to_dict()
    qa["Q1_n_by_config_k4_nonrev"] = {k: int(v) for k, v in sorted(q1_n_by_cfg.items())}

    for raw_col, metric_name in q1_metrics:
        for cfg in q1_cfgs:
            a = finite_array(q1_df.loc[q1_df["config_name"] == cfg, raw_col])
            for ctrl in q1_ctrls:
                b = finite_array(q1_df.loc[q1_df["config_name"] == ctrl, raw_col])
                support = f"{cfg} N={a.size}; {ctrl} N={b.size}"
                add_row(
                    question_id="Q1",
                    analysis_id=f"Q1_{cfg}_vs_{ctrl}_{metric_name}",
                    n=256,
                    group_A=cfg,
                    group_B=ctrl,
                    metric=metric_name,
                    A=a,
                    Bvals=b,
                    data_scope=q1_scope,
                    support_note=support,
                    rng=base_rng,
                )

        # aggregated competition group on each metric
        comp = finite_array(q1_df.loc[q1_df["config_name"].isin(q1_cfgs), raw_col])
        for ctrl in q1_ctrls:
            b = finite_array(q1_df.loc[q1_df["config_name"] == ctrl, raw_col])
            support = f"competition_group N={comp.size}; {ctrl} N={b.size}; A16_only partial seeds"
            add_row(
                question_id="Q1",
                analysis_id=f"Q1_competition_group_vs_{ctrl}_{metric_name}",
                n=256,
                group_A="competition_group(A14/A16/A17)",
                group_B=ctrl,
                metric=metric_name,
                A=comp,
                Bvals=b,
                data_scope=q1_scope,
                support_note=support,
                rng=base_rng,
            )

    # Plot Q1
    fig_q1, ax_q1 = plt.subplots(figsize=(8.2, 4.8))
    order_q1 = ["baseline", "full_action", "A14_only", "A16_only", "A17_only"]
    y_by_cfg = [finite_array(q1_df.loc[q1_df["config_name"] == cfg, "lagr_diff_kl"]) for cfg in order_q1]
    ax_q1.boxplot(y_by_cfg, tick_labels=order_q1, showfliers=False)
    for i, arr in enumerate(y_by_cfg, start=1):
        jittered_scatter(ax_q1, float(i), arr, base_rng)
        top = np.nanmax(arr) if arr.size else 0.0
        ax_q1.text(i, top + 0.01, f"N={arr.size}", ha="center", va="bottom", fontsize=8)
    ax_q1.set_ylabel(r"$\mathrm{KL}^{\star}_{\mathrm{diff}}$ at $k=4$")
    ax_q1.set_title("N3 Q1: Partition-competition survival (n=256, REV excluded)")
    fig_q1.tight_layout()
    out_q1 = Path(args.outdir_fig) / "N3_Q1_partition_competition.pdf"
    ensure_parent(out_q1)
    fig_q1.savefig(out_q1)
    plt.close(fig_q1)

    # Q2: generators vs full_action
    q2_scope = "ds_exp112_wave2_n256_selective_unique + ds_exp107_wave2_n256_sweep"
    q2_df = run[run["n"] == 256].copy()
    gen_cfgs = ["gen3_A13_A14_A19", "gen4_core"]
    q2_metrics = [
        ("tilde_frob", "tilde_frob", False),
        ("tilde_sigma_pi", "tilde_sigma_pi_log10p1", True),
        ("tilde_geo_r2", "tilde_geo_r2", False),
        ("tilde_diff_kl", "tilde_diff_kl", False),
    ]
    q2_plot_data: Dict[str, List[Tuple[str, float, float, float]]] = defaultdict(list)

    for col, metric_name, use_log in q2_metrics:
        full_vals_raw = q2_df.loc[q2_df["config_name"] == "full_action", col]
        full_vals = log10p1_nonneg(full_vals_raw) if use_log else finite_array(full_vals_raw)
        for cfg in gen_cfgs:
            a_raw = q2_df.loc[q2_df["config_name"] == cfg, col]
            a = log10p1_nonneg(a_raw) if use_log else finite_array(a_raw)
            support = f"{cfg} N={a.size}; full_action N={full_vals.size}"
            aid = f"Q2_{cfg}_vs_full_action_{metric_name}"
            add_row(
                question_id="Q2",
                analysis_id=aid,
                n=256,
                group_A=cfg,
                group_B="full_action",
                metric=metric_name,
                A=a,
                Bvals=full_vals,
                data_scope=q2_scope,
                support_note=support,
                rng=base_rng,
            )
            row = rows[-1]
            q2_plot_data[metric_name].append((cfg, row["delta_median"], row["ci_low"], row["ci_high"]))

    # Plot Q2
    fig_q2, axes_q2 = plt.subplots(2, 2, figsize=(9.4, 6.4))
    metric_titles = [
        "tilde_frob",
        "tilde_sigma_pi_log10p1",
        "tilde_geo_r2",
        "tilde_diff_kl",
    ]
    for ax, metric_name in zip(axes_q2.ravel(), metric_titles):
        data = q2_plot_data[metric_name]
        xs = np.arange(len(data))
        ys = np.array([d[1] for d in data], dtype=float)
        lo = np.array([d[2] for d in data], dtype=float)
        hi = np.array([d[3] for d in data], dtype=float)
        yerr = np.vstack([ys - lo, hi - ys])
        ax.errorbar(xs, ys, yerr=yerr, fmt="o")
        ax.axhline(0.0, linewidth=0.8)
        ax.set_xticks(xs)
        ax.set_xticklabels([d[0] for d in data], rotation=15)
        ax.set_title(metric_name)
        ax.set_ylabel(r"$\Delta$ (generator - full_action)")
    fig_q2.suptitle("N3 Q2: Generator deltas vs full_action (n=256)")
    fig_q2.tight_layout()
    out_q2 = Path(args.outdir_fig) / "N3_Q2_generators_vs_full.pdf"
    fig_q2.savefig(out_q2)
    plt.close(fig_q2)

    # Q3: scale trends
    q3_scope = "ds_exp112_wave3_n32_64_128_all + ds_exp107_wave2_n256_sweep + ds_exp112_wave2_n256_selective_unique"
    q3_cfgs = [
        "baseline",
        "full_action",
        "full_all",
        "gen3_A13_A14_A19",
        "gen4_core",
        "A14_only",
        "A16_only",
        "A17_only",
    ]
    q3_metrics = [
        ("tilde_sigma_pi", "tilde_sigma_pi_log10p1", True),
        ("tilde_geo_r2", "tilde_geo_r2", False),
        ("tilde_diff_kl", "tilde_diff_kl", False),
        ("tilde_frob", "tilde_frob", False),
    ]
    q3_summ: Dict[Tuple[str, str, int], Tuple[np.ndarray, float, float, float]] = {}

    n_order = [32, 64, 128, 256]
    for cfg in q3_cfgs:
        for col, metric_name, use_log in q3_metrics:
            for nval in n_order:
                raw = run.loc[(run["config_name"] == cfg) & (run["n"] == nval), col]
                arr = log10p1_nonneg(raw) if use_log else finite_array(raw)
                med, lo, hi = bootstrap_median_ci(arr, B, base_rng)
                q3_summ[(cfg, metric_name, nval)] = (arr, med, lo, hi)
                rows.append(
                    {
                        "question_id": "Q3",
                        "analysis_id": f"Q3_{cfg}_{metric_name}_n{nval}_median",
                        "n": nval,
                        "group_A": cfg,
                        "group_B": "",
                        "metric": metric_name,
                        "N_A": int(arr.size),
                        "N_B": 0,
                        "median_A": med,
                        "median_B": math.nan,
                        "delta_median": math.nan,
                        "ci_low": lo,
                        "ci_high": hi,
                        "ES_MAD": math.nan,
                        "support_note": f"{cfg} n={nval} N={arr.size}",
                        "data_scope": q3_scope,
                    }
                )

            arr256 = q3_summ[(cfg, metric_name, 256)][0]
            arr128 = q3_summ[(cfg, metric_name, 128)][0]
            dmed, lo, hi = bootstrap_delta_ci(arr256, arr128, B, base_rng)
            rows.append(
                {
                    "question_id": "Q3",
                    "analysis_id": f"Q3_{cfg}_{metric_name}_delta256m128",
                    "n": 256,
                    "group_A": f"{cfg}@256",
                    "group_B": f"{cfg}@128",
                    "metric": metric_name,
                    "N_A": int(arr256.size),
                    "N_B": int(arr128.size),
                    "median_A": float(np.median(arr256)) if arr256.size else math.nan,
                    "median_B": float(np.median(arr128)) if arr128.size else math.nan,
                    "delta_median": dmed,
                    "ci_low": lo,
                    "ci_high": hi,
                    "ES_MAD": es_mad(arr256, arr128),
                    "support_note": f"{cfg}: n256 N={arr256.size}, n128 N={arr128.size}",
                    "data_scope": q3_scope,
                }
            )

            # Convergence-to-baseline |delta| change from n128 to n256
            if cfg != "baseline":
                c128 = arr128
                c256 = arr256
                b128 = q3_summ[("baseline", metric_name, 128)][0]
                b256 = q3_summ[("baseline", metric_name, 256)][0]
                if c128.size and c256.size and b128.size and b256.size:
                    obs = abs(float(np.median(c256) - np.median(b256))) - abs(float(np.median(c128) - np.median(b128)))
                    if min(c128.size, c256.size, b128.size, b256.size) > 0:
                        i_c256 = base_rng.integers(0, c256.size, size=(B, c256.size))
                        i_b256 = base_rng.integers(0, b256.size, size=(B, b256.size))
                        i_c128 = base_rng.integers(0, c128.size, size=(B, c128.size))
                        i_b128 = base_rng.integers(0, b128.size, size=(B, b128.size))
                        ds = np.abs(np.median(c256[i_c256], axis=1) - np.median(b256[i_b256], axis=1)) - np.abs(
                            np.median(c128[i_c128], axis=1) - np.median(b128[i_b128], axis=1)
                        )
                        lo2, hi2 = np.percentile(ds, [2.5, 97.5])
                    else:
                        lo2, hi2 = (math.nan, math.nan)
                    rows.append(
                        {
                            "question_id": "Q3",
                            "analysis_id": f"Q3_{cfg}_{metric_name}_absDeltaVsBaseline_change256m128",
                            "n": 256,
                            "group_A": f"|{cfg}-baseline|@256",
                            "group_B": f"|{cfg}-baseline|@128",
                            "metric": metric_name,
                            "N_A": int(c256.size),
                            "N_B": int(c128.size),
                            "median_A": abs(float(np.median(c256) - np.median(b256))),
                            "median_B": abs(float(np.median(c128) - np.median(b128))),
                            "delta_median": obs,
                            "ci_low": float(lo2),
                            "ci_high": float(hi2),
                            "ES_MAD": math.nan,
                            "support_note": f"{cfg} vs baseline convergence sign: negative means closer at 256",
                            "data_scope": q3_scope,
                        }
                    )

    # fingerprint equivalence sanity (controls)
    controls = ["baseline", "full_action", "full_all"]
    fp_report = {}
    for cfg in controls:
        fp_report[cfg] = {}
        for exp_id, nval in [("EXP-107", 256), ("EXP-112", 128)]:
            subset = run[(run["exp_id"] == exp_id) & (run["n"] == nval) & (run["config_name"] == cfg)]
            paths = sorted(subset["log_file"].dropna().astype(str).unique().tolist())
            if not paths:
                fp_report[cfg][f"{exp_id}_n{nval}"] = {"fingerprint": None, "enabled_count": None, "log_file": None}
                continue
            cells, fp = load_enabled_from_log(paths[0])
            fp_report[cfg][f"{exp_id}_n{nval}"] = {
                "fingerprint": fp,
                "enabled_count": None if cells is None else len(cells),
                "log_file": paths[0],
            }
        a = fp_report[cfg]["EXP-107_n256"]["fingerprint"]
        b = fp_report[cfg]["EXP-112_n128"]["fingerprint"]
        fp_report[cfg]["match_exp107_n256_vs_exp112_n128"] = (a is not None and b is not None and a == b)
    qa["Q3_control_fingerprints"] = fp_report

    # Plot Q3: delta vs baseline for 2 metrics
    fig_q3, axes_q3 = plt.subplots(1, 2, figsize=(10.0, 4.6), sharex=True)
    line_metrics = ["tilde_sigma_pi_log10p1", "tilde_geo_r2"]
    for ax, metric_name in zip(axes_q3, line_metrics):
        baseline_vals = {}
        for nval in n_order:
            baseline_vals[nval] = q3_summ[("baseline", metric_name, nval)][1]
        for cfg in q3_cfgs:
            if cfg == "baseline":
                continue
            xs: List[int] = []
            ys: List[float] = []
            for nval in n_order:
                med_cfg = q3_summ[(cfg, metric_name, nval)][1]
                med_base = baseline_vals[nval]
                if math.isfinite(med_cfg) and math.isfinite(med_base):
                    xs.append(nval)
                    ys.append(med_cfg - med_base)
            if xs:
                ax.plot(xs, ys, marker="o", label=cfg)
        ax.axhline(0.0, linewidth=0.8)
        ax.set_title(f"{metric_name} Δ vs baseline")
        ax.set_xlabel("n")
        ax.set_ylabel(r"$\Delta$ median")
        ax.set_xticks(n_order)
    axes_q3[1].legend(fontsize=7, ncol=1, frameon=False)
    fig_q3.suptitle("N3 Q3: Scale trends (no interpolation over missing points)")
    fig_q3.tight_layout()
    out_q3 = Path(args.outdir_fig) / "N3_Q3_scale_trends.pdf"
    fig_q3.savefig(out_q3)
    plt.close(fig_q3)

    # Q4: REV rate
    q4_scope = "all manifest-selected datasets"
    rev_by_n = {}
    for nval in [32, 64, 128, 256]:
        sub = run[run["n"] == nval]
        n_total = int(len(sub))
        rev_count = int(sub["is_REV"].sum())
        rate, lo, hi = wilson_ci(rev_count, n_total)
        rev_by_n[nval] = {"N_total": n_total, "REV_count": rev_count, "REV_rate": rate, "ci_low": lo, "ci_high": hi}
        rows.append(
            {
                "question_id": "Q4",
                "analysis_id": f"Q4_REV_rate_n{nval}_overall",
                "n": nval,
                "group_A": f"n={nval} overall",
                "group_B": "",
                "metric": "is_REV_rate",
                "N_A": n_total,
                "N_B": 0,
                "median_A": rate,
                "median_B": math.nan,
                "delta_median": math.nan,
                "ci_low": lo,
                "ci_high": hi,
                "ES_MAD": math.nan,
                "support_note": f"REV_count={rev_count}",
                "data_scope": q4_scope,
            }
        )

    n256 = run[run["n"] == 256]
    rev_cfg_rows = {}
    for cfg, sub in sorted(n256.groupby("config_name"), key=lambda x: x[0]):
        n_total = int(len(sub))
        rev_count = int(sub["is_REV"].sum())
        rate, lo, hi = wilson_ci(rev_count, n_total)
        rev_cfg_rows[cfg] = {"N_total": n_total, "REV_count": rev_count, "REV_rate": rate}
        rows.append(
            {
                "question_id": "Q4",
                "analysis_id": f"Q4_REV_rate_n256_{cfg}",
                "n": 256,
                "group_A": cfg,
                "group_B": "n=256",
                "metric": "is_REV_rate",
                "N_A": n_total,
                "N_B": 0,
                "median_A": rate,
                "median_B": math.nan,
                "delta_median": math.nan,
                "ci_low": lo,
                "ci_high": hi,
                "ES_MAD": math.nan,
                "support_note": f"REV_count={rev_count}",
                "data_scope": q4_scope,
            }
        )
    qa["Q4_rev_by_n"] = rev_by_n
    qa["Q4_rev_by_config_n256"] = rev_cfg_rows

    fig_q4, ax_q4 = plt.subplots(figsize=(6.6, 4.2))
    x = np.array([32, 64, 128, 256], dtype=int)
    y = np.array([rev_by_n[int(n)]["REV_rate"] for n in x], dtype=float)
    lo = np.array([rev_by_n[int(n)]["ci_low"] for n in x], dtype=float)
    hi = np.array([rev_by_n[int(n)]["ci_high"] for n in x], dtype=float)
    yerr = np.vstack([y - lo, hi - y])
    ax_q4.bar(x.astype(str), y)
    ax_q4.errorbar(np.arange(len(x)), y, yerr=yerr, fmt="none")
    ax_q4.set_ylim(0, max(0.05, float(np.nanmax(hi) * 1.2)))
    ax_q4.set_ylabel("REV rate")
    ax_q4.set_title("N3 Q4: REV rate by n (overall)")
    for i, nval in enumerate(x):
        rec = rev_by_n[int(nval)]
        ax_q4.text(i, y[i] + 0.003, f"{rec['REV_count']}/{rec['N_total']}", ha="center", va="bottom", fontsize=8)
    fig_q4.tight_layout()
    out_q4 = Path(args.outdir_fig) / "N3_Q4_REV_rate.pdf"
    fig_q4.savefig(out_q4)
    plt.close(fig_q4)

    # Q5: structural interference paradox
    q5_scope = "ds_expf1_wave2_n256_empty + ds_exp107_wave2_n256_sweep + ds_exp112_wave2_n256_selective_unique"
    run256 = run[run["n"] == 256].copy()
    cfg_stats = []
    enabled_info = {}
    for cfg, sub in sorted(run256.groupby("config_name"), key=lambda x: x[0]):
        med_frob = float(np.median(finite_array(sub["tilde_frob"])))
        paths = sorted(sub["log_file"].dropna().astype(str).unique().tolist())
        cells = None
        fp = None
        used = None
        for path in paths:
            cells_try, fp_try = load_enabled_from_log(path)
            if cells_try is not None:
                cells = cells_try
                fp = fp_try
                used = path
                break
        enabled_count = None if cells is None else len(cells)
        cfg_stats.append(
            {
                "config_name": cfg,
                "enabled_count": enabled_count,
                "tilde_frob_median": med_frob,
                "N_runs": int(len(sub)),
            }
        )
        enabled_info[cfg] = {
            "enabled_count": enabled_count,
            "enabled_fingerprint": fp,
            "log_file_used": used,
        }

    cfg_df = pd.DataFrame(cfg_stats).dropna(subset=["enabled_count", "tilde_frob_median"])
    xvals = cfg_df["enabled_count"].to_numpy(dtype=float)
    yvals = cfg_df["tilde_frob_median"].to_numpy(dtype=float)
    rho, pval = spearman_perm_pvalue(xvals, yvals, P, base_rng)
    rows.append(
        {
            "question_id": "Q5",
            "analysis_id": "Q5_spearman_enabledcount_vs_tilde_frob_n256",
            "n": 256,
            "group_A": "enabled_count",
            "group_B": "tilde_frob(config_median)",
            "metric": "spearman_enabledcount_vs_tilde_frob",
            "N_A": int(len(xvals)),
            "N_B": int(len(yvals)),
            "median_A": float(np.median(xvals)) if xvals.size else math.nan,
            "median_B": float(np.median(yvals)) if yvals.size else math.nan,
            "delta_median": rho,
            "ci_low": math.nan,
            "ci_high": math.nan,
            "ES_MAD": math.nan,
            "support_note": f"permutation_p={pval:.6g}",
            "data_scope": q5_scope,
        }
    )

    full_frob = finite_array(run256.loc[run256["config_name"] == "full_action", "tilde_frob"])
    for cfg in ["gen3_A13_A14_A19", "gen4_core"]:
        a = finite_array(run256.loc[run256["config_name"] == cfg, "tilde_frob"])
        add_row(
            question_id="Q5",
            analysis_id=f"Q5_{cfg}_vs_full_action_tilde_frob",
            n=256,
            group_A=cfg,
            group_B="full_action",
            metric="tilde_frob",
            A=a,
            Bvals=full_frob,
            data_scope=q5_scope,
            support_note=f"{cfg} N={a.size}; full_action N={full_frob.size}",
            rng=base_rng,
        )

    qa["Q5_enabled_info_by_config"] = enabled_info
    qa["Q5_spearman"] = {"rho": rho, "perm_pvalue": pval, "n_configs": int(len(xvals))}

    fig_q5, ax_q5 = plt.subplots(figsize=(7.0, 4.8))
    ax_q5.scatter(xvals, yvals, s=28)
    if xvals.size >= 2:
        coef = np.polyfit(xvals, yvals, 1)
        xx = np.linspace(float(np.min(xvals)), float(np.max(xvals)), 100)
        yy = coef[0] * xx + coef[1]
        ax_q5.plot(xx, yy)
    key_cfgs = {"baseline", "full_action", "full_all", "gen3_A13_A14_A19", "gen4_core", "A14_only"}
    for _, r in cfg_df.iterrows():
        cfg = str(r["config_name"])
        if cfg in key_cfgs:
            ax_q5.text(float(r["enabled_count"]) + 0.2, float(r["tilde_frob_median"]), cfg, fontsize=8)
    ax_q5.set_xlabel("enabled cell count |E|")
    ax_q5.set_ylabel(r"median $\tilde{\mathrm{frob}}$ (n=256)")
    ax_q5.set_title("N3 Q5: enabled-count vs structure (n=256)")
    fig_q5.tight_layout()
    out_q5 = Path(args.outdir_fig) / "N3_Q5_interference_enabledcount.pdf"
    fig_q5.savefig(out_q5)
    plt.close(fig_q5)

    # Write analysis CSV
    out_csv = Path(args.out_csv)
    ensure_parent(out_csv)
    columns = [
        "question_id",
        "analysis_id",
        "n",
        "group_A",
        "group_B",
        "metric",
        "N_A",
        "N_B",
        "median_A",
        "median_B",
        "delta_median",
        "ci_low",
        "ci_high",
        "ES_MAD",
        "support_note",
        "data_scope",
    ]
    rows_sorted = sorted(rows, key=lambda r: (r["question_id"], r["analysis_id"]))
    with gzip.open(out_csv, "wt", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        for r in rows_sorted:
            writer.writerow(r)

    qa["rows_total"] = len(rows_sorted)
    qa["rows_by_question"] = dict(sorted(Counter(r["question_id"] for r in rows_sorted).items()))

    # Build memo with required headings and analysis-id references
    rows_df = pd.DataFrame(rows_sorted)
    def get_row(analysis_id: str) -> pd.Series:
        m = rows_df[rows_df["analysis_id"] == analysis_id]
        if m.empty:
            return pd.Series(dtype=float)
        return m.iloc[0]

    q1_ref = "Q1_competition_group_vs_full_action_lagr_diff_kl_k4"
    q2_ref = "Q2_gen3_A13_A14_A19_vs_full_action_tilde_diff_kl"
    q3_ref = "Q3_full_action_tilde_geo_r2_delta256m128"
    q4_ref = "Q4_REV_rate_n256_overall"
    q5_ref = "Q5_gen3_A13_A14_A19_vs_full_action_tilde_frob"

    r1 = get_row(q1_ref)
    r2 = get_row(q2_ref)
    r3 = get_row(q3_ref)
    r4 = get_row(q4_ref)
    r5 = get_row(q5_ref)

    def classify(row: pd.Series, positive_good: bool = True) -> str:
        if row.empty or not math.isfinite(float(row.get("delta_median", math.nan))):
            return "same"
        d = float(row["delta_median"])
        lo = float(row.get("ci_low", math.nan))
        hi = float(row.get("ci_high", math.nan))
        if math.isfinite(lo) and math.isfinite(hi):
            if lo > 0 or hi < 0:
                return "strengthens" if (d > 0) == positive_good else "weakens"
        return "same"

    q1_cls = classify(r1, positive_good=True)
    q2_cls = classify(r2, positive_good=False)  # lower diff_kl vs full_action favored
    q3_cls = classify(r3, positive_good=True)
    q4_cls = "same"
    if not r4.empty and math.isfinite(float(r4.get("median_A", math.nan))):
        q4_cls = "same" if float(r4["median_A"]) <= 0.01 else "weakens"
    q5_cls = classify(r5, positive_good=True)

    trunc_note = manifest.get("notes", {}).get("wave2_truncation_count", "unknown")
    affected_cfgs = ["A14_only", "A16_only", "A17_only", "gen3_A13_A14_A19", "gen4_core", "loo_A13", "loo_A14", "loo_A18", "loo_A19", "fa_no_P1row", "fa_no_P2mod", "fa_no_P3row", "baseline", "full_action"]

    memo_lines = [
        "Q1 Partition competition survival:",
        f"At n=256 (k=4, REV excluded), competition-group diffusion misfit relative to full_action is quantified by `{q1_ref}` with delta={r1.get('delta_median', float('nan')):.4g} and CI=[{r1.get('ci_low', float('nan')):.4g},{r1.get('ci_high', float('nan')):.4g}].",
        f"- Decision: **{q1_cls}** (trace: `{q1_ref}`).",
        "",
        "Q2 gen3 vs full_action:",
        f"Generator deltas vs full_action are summarized in rows including `{q2_ref}` and `Q2_gen4_core_vs_full_action_tilde_diff_kl`; effect signs are mixed but quantifiable with bootstrap CIs.",
        f"- Decision: **{q2_cls}** (trace: `{q2_ref}`).",
        "",
        "Q3 Scale trend direction:",
        f"Cross-scale shifts are captured by rows like `{q3_ref}` and related `Q3_*_delta256m128` entries; trends are configuration-dependent rather than uniformly convergent.",
        f"- Decision: **{q3_cls}** (trace: `{q3_ref}`).",
        "",
        "Q4 REV rate at n=256:",
        f"Overall REV prevalence at n=256 is reported in `{q4_ref}` with rate={r4.get('median_A', float('nan')):.4g} and Wilson CI=[{r4.get('ci_low', float('nan')):.4g},{r4.get('ci_high', float('nan')):.4g}].",
        f"- Decision: **{q4_cls}** (trace: `{q4_ref}`).",
        "",
        "Q5 Structural interference paradox:",
        f"Paradox checks include generator-vs-full_action rows `{q5_ref}` and `Q5_gen4_core_vs_full_action_tilde_frob`, plus enabled-count correlation `Q5_spearman_enabledcount_vs_tilde_frob_n256`.",
        f"- Decision: **{q5_cls}** (trace: `{q5_ref}`).",
        "",
        "Caveats:",
        f"- Wave_2 truncation persists: {trunc_note} logs missing audits, causing incomplete seed coverage in EXP-112 selective n=256 configs.",
        f"- Most affected config family: {', '.join(affected_cfgs)}.",
        "- A16_only has the smallest support (5 seeds), and several selective configs have 7-9 seeds rather than 10.",
    ]

    out_memo = Path(args.out_memo)
    ensure_parent(out_memo)
    out_memo.write_text("\n".join(memo_lines) + "\n", encoding="utf-8")

    # Write QA
    out_qa = Path(args.qa_out)
    ensure_parent(out_qa)
    with out_qa.open("w", encoding="utf-8") as fh:
        json.dump(qa, fh, indent=2, sort_keys=True)

    print(f"wrote={out_csv}")
    print(f"wrote={out_q1}")
    print(f"wrote={out_q2}")
    print(f"wrote={out_q3}")
    print(f"wrote={out_q4}")
    print(f"wrote={out_q5}")
    print(f"wrote={out_memo}")
    print(f"wrote={out_qa}")
    print(f"rows_total={len(rows_sorted)}")
    print(f"rows_by_question={qa['rows_by_question']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
