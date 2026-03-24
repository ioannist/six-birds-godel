#!/usr/bin/env python3
"""Generate F4 plots (Lagrange probes vs resolution rung)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent))
from plot_common import MIN_SUPPORT, METRIC_LABELS, filter_min_support, rungs_for_n


CONFIGS = ["baseline", "full_action", "full_all"]

PANELS = [
    {
        "id": "F4a",
        "metric": "pla2_gap",
        "ylabel": METRIC_LABELS["pla2_gap"],
        "pdf_name": "F4a_PLA2_n{n}.pdf",
        "stats_name": "F4a_stats_n{n}.csv.gz",
    },
    {
        "id": "F4b",
        "metric": "step_entropy",
        "ylabel": METRIC_LABELS["step_entropy"],
        "pdf_name": "F4b_step_entropy_n{n}.pdf",
        "stats_name": "F4b_stats_n{n}.csv.gz",
    },
    {
        "id": "F4c",
        "metric": "lagr_geo_r2",
        "ylabel": METRIC_LABELS["lagr_geo_r2"],
        "pdf_name": "F4c_geo_r2_n{n}.pdf",
        "stats_name": "F4c_stats_n{n}.csv.gz",
    },
    {
        "id": "F4d",
        "metric": "lagr_diff_kl",
        "ylabel": METRIC_LABELS["lagr_diff_kl"],
        "pdf_name": "F4d_diff_kl_n{n}.pdf",
        "stats_name": "F4d_stats_n{n}.csv.gz",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate F4 plots for Lagrange probes.")
    parser.add_argument("--in", dest="in_path", default="paper/figdata/scan_rung_table.csv.gz")
    parser.add_argument("--outdir", default="paper/fig")
    parser.add_argument("--figdata_outdir", default="paper/figdata")
    parser.add_argument("--min_support", type=int, default=MIN_SUPPORT)
    parser.add_argument("--n", type=int, default=128)
    return parser.parse_args()


def _complete_support_grid(agg_df: pd.DataFrame, rungs: list[int]) -> pd.DataFrame:
    idx = pd.MultiIndex.from_product([CONFIGS, rungs], names=["config_name", "k_rung"])
    out = agg_df.set_index(["config_name", "k_rung"]).reindex(idx).reset_index()
    out["n_valid"] = pd.to_numeric(out["n_valid"], errors="coerce").fillna(0).astype(int)
    return out


def _aggregate_metric(n_df: pd.DataFrame, metric_col: str) -> tuple[pd.DataFrame, dict]:
    work = n_df.copy()
    work[metric_col] = pd.to_numeric(work[metric_col], errors="coerce")

    missingness = {}
    for cfg in CONFIGS:
        c = work[work["config_name"] == cfg][metric_col]
        total = int(c.shape[0])
        if total == 0:
            missingness[cfg] = None
        else:
            missingness[cfg] = float(c.isna().sum() / total)

    finite = work[work[metric_col].notna()].copy()
    grouped = (
        finite.groupby(["config_name", "k_rung"], as_index=False)
        .agg(
            median=(metric_col, "median"),
            q25=(metric_col, lambda s: s.quantile(0.25)),
            q75=(metric_col, lambda s: s.quantile(0.75)),
            n_valid=(metric_col, "count"),
        )
    )
    if not grouped.empty:
        grouped["k_rung"] = grouped["k_rung"].astype(int)
        grouped["n_valid"] = grouped["n_valid"].astype(int)
    return grouped, missingness


def _build_qa_panel(
    panel_id: str,
    agg_df: pd.DataFrame,
    kept_df: pd.DataFrame,
    rungs: list[int],
    min_support: int,
    missingness: dict,
) -> dict:
    grid = _complete_support_grid(agg_df, rungs)
    panel_qa = {}

    kept_counts = {}
    for cfg in CONFIGS:
        c_grid = grid[grid["config_name"] == cfg].copy()
        c_kept = kept_df[kept_df["config_name"] == cfg].copy()
        rungs_kept = sorted(int(x) for x in c_kept["k_rung"].tolist())
        rungs_dropped = sorted(int(x) for x in c_grid[c_grid["n_valid"] < min_support]["k_rung"].tolist())
        supports = c_grid["n_valid"].tolist()
        kept_counts[cfg] = len(rungs_kept)
        panel_qa[cfg] = {
            "rungs_kept": rungs_kept,
            "rungs_dropped_support": rungs_dropped,
            "min_n_valid": int(min(supports)) if supports else None,
            "median_n_valid": float(pd.Series(supports).median()) if supports else None,
            "max_n_valid": int(max(supports)) if supports else None,
            "overall_missingness_rate": missingness.get(cfg),
        }

    panel_qa["_panel_support_proxy"] = {
        "has_any_config_with_at_least_2_rungs": any(v >= 2 for v in kept_counts.values()),
        "all_configs_have_at_least_1_rung": all(v >= 1 for v in kept_counts.values()),
    }
    return panel_qa


def _plot_panel(
    kept_df: pd.DataFrame,
    ylabel: str,
    rungs: list[int],
    out_path: Path,
) -> None:
    plt.figure(figsize=(7.2, 4.6))
    for cfg in CONFIGS:
        c = kept_df[kept_df["config_name"] == cfg].sort_values("k_rung")
        if c.empty:
            plt.plot([], [], label=cfg)
            continue
        y = c["median"].to_numpy()
        yerr_lo = (c["median"] - c["q25"]).to_numpy()
        yerr_hi = (c["q75"] - c["median"]).to_numpy()
        plt.errorbar(
            c["k_rung"].to_numpy(),
            y,
            yerr=[yerr_lo, yerr_hi],
            marker="o",
            capsize=3,
            label=cfg,
        )

    plt.xlabel(METRIC_LABELS["x_k_rung"])
    plt.ylabel(ylabel)
    plt.xticks(rungs)
    plt.legend()
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path)
    plt.close()


if __name__ == "__main__":
    args = parse_args()
    in_path = Path(args.in_path)
    outdir = Path(args.outdir)
    figdata_outdir = Path(args.figdata_outdir)
    min_support = args.min_support
    n_value = args.n

    outdir.mkdir(parents=True, exist_ok=True)
    figdata_outdir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(in_path)
    df = df[
        (pd.to_numeric(df["n"], errors="coerce") == n_value)
        & (df["config_name"].isin(CONFIGS))
    ].copy()
    df["k_rung"] = pd.to_numeric(df["k_rung"], errors="coerce")
    df = df.dropna(subset=["k_rung"]).copy()
    df["k_rung"] = df["k_rung"].astype(int)

    rungs = rungs_for_n(n_value)
    qa_path = figdata_outdir / "F4_QA.json"
    if qa_path.exists():
        with open(qa_path, "r", encoding="utf-8") as fh:
            qa_all = json.load(fh)
            if not isinstance(qa_all, dict):
                qa_all = {}
    else:
        qa_all = {}

    qa_all[f"n{n_value}"] = {"min_support": min_support, "panels": {}}

    for panel in PANELS:
        metric = panel["metric"]
        agg_df, missingness = _aggregate_metric(df, metric)
        kept_df = filter_min_support(agg_df, support_col="n_valid", min_support=min_support)
        kept_df = kept_df.sort_values(["config_name", "k_rung"]).reset_index(drop=True)

        stats_out = figdata_outdir / panel["stats_name"].format(n=n_value)
        kept_df.to_csv(stats_out, index=False, compression="gzip")

        pdf_out = outdir / panel["pdf_name"].format(n=n_value)
        _plot_panel(kept_df, panel["ylabel"], rungs, pdf_out)

        qa_all[f"n{n_value}"]["panels"][panel["id"]] = _build_qa_panel(
            panel["id"], agg_df, kept_df, rungs, min_support, missingness
        )

    with open(qa_path, "w", encoding="utf-8") as fh:
        json.dump(qa_all, fh, indent=2, sort_keys=True)

    print(f"wrote F4 outputs for n={n_value}")
