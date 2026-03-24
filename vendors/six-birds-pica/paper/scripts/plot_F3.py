#!/usr/bin/env python3
"""Generate F3 plots (structure + arrow-of-time vs resolution rung)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent))
from plot_common import (
    MIN_SUPPORT,
    METRIC_LABELS,
    filter_min_support,
    rungs_for_n,
    sigma_pi_to_log10p1,
)


CONFIGS = ["empty", "baseline", "full_action", "full_all"]
N_VALUES = [32, 64, 128, 256]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate F3 Physica-A-ready figures.")
    parser.add_argument("--in", dest="in_path", default="paper/figdata/scan_rung_table.csv.gz")
    parser.add_argument("--outdir", default="paper/fig")
    parser.add_argument("--figdata_outdir", default="paper/figdata")
    parser.add_argument("--min_support", type=int, default=MIN_SUPPORT)
    return parser.parse_args()


def _aggregate_metric(df: pd.DataFrame, metric_col: str) -> pd.DataFrame:
    work = df.copy()
    work[metric_col] = pd.to_numeric(work[metric_col], errors="coerce")
    grouped = (
        work.groupby(["config_name", "k_rung"], as_index=False)
        .agg(
            median=(metric_col, "median"),
            q25=(metric_col, lambda s: s.quantile(0.25)),
            q75=(metric_col, lambda s: s.quantile(0.75)),
            n_valid=(metric_col, lambda s: int(s.notna().sum())),
        )
    )
    grouped["k_rung"] = grouped["k_rung"].astype(int)
    return grouped


def _complete_support_grid(agg_df: pd.DataFrame, rungs: list[int]) -> pd.DataFrame:
    idx = pd.MultiIndex.from_product([CONFIGS, rungs], names=["config_name", "k_rung"])
    out = agg_df.set_index(["config_name", "k_rung"]).reindex(idx).reset_index()
    out["n_valid"] = pd.to_numeric(out["n_valid"], errors="coerce").fillna(0).astype(int)
    return out


def _build_qa_for_plot(
    agg_df: pd.DataFrame,
    kept_df: pd.DataFrame,
    rungs: list[int],
    min_support: int,
) -> dict:
    qa = {}
    grid = _complete_support_grid(agg_df, rungs)
    for config in CONFIGS:
        c_grid = grid[grid["config_name"] == config].copy()
        c_kept = kept_df[kept_df["config_name"] == config].copy()
        plotted = sorted(int(x) for x in c_kept["k_rung"].tolist())
        dropped = sorted(int(x) for x in c_grid[c_grid["n_valid"] < min_support]["k_rung"].tolist())
        supports = c_grid["n_valid"].tolist()
        if supports:
            support_min = int(min(supports))
            support_median = float(pd.Series(supports).median())
            support_max = int(max(supports))
        else:
            support_min = None
            support_median = None
            support_max = None
        qa[config] = {
            "rungs_plotted": plotted,
            "rungs_dropped_low_support": dropped,
            "n_valid_min": support_min,
            "n_valid_median": support_median,
            "n_valid_max": support_max,
        }
    return qa


def _plot_metric(
    kept_df: pd.DataFrame,
    n_value: int,
    ylabel: str,
    out_path: Path,
) -> None:
    rungs = rungs_for_n(n_value)
    plt.figure(figsize=(7.2, 4.6))
    for config in CONFIGS:
        c = kept_df[kept_df["config_name"] == config].sort_values("k_rung")
        if c.empty:
            plt.plot([], [], label=config)
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
            label=config,
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
    min_support = args.min_support

    in_path = Path(args.in_path)
    outdir = Path(args.outdir)
    figdata_outdir = Path(args.figdata_outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    figdata_outdir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(in_path)
    df = df[df["config_name"].isin(CONFIGS)].copy()
    df["n"] = pd.to_numeric(df["n"], errors="coerce").astype("Int64")
    df["k_rung"] = pd.to_numeric(df["k_rung"], errors="coerce").astype("Int64")
    df = df.dropna(subset=["n", "k_rung"]).copy()
    df["n"] = df["n"].astype(int)
    df["k_rung"] = df["k_rung"].astype(int)

    qa = {}

    for n_value in N_VALUES:
        n_df = df[df["n"] == n_value].copy()
        rungs = rungs_for_n(n_value)

        # F3a: frob
        f3a_agg = _aggregate_metric(n_df, "frob")
        f3a_kept = filter_min_support(f3a_agg, support_col="n_valid", min_support=min_support)
        f3a_kept = f3a_kept.sort_values(["config_name", "k_rung"]).reset_index(drop=True)
        f3a_kept.to_csv(
            figdata_outdir / f"F3a_stats_n{n_value}.csv.gz",
            index=False,
            compression="gzip",
        )
        _plot_metric(
            f3a_kept,
            n_value,
            METRIC_LABELS["frob"],
            outdir / f"F3a_n{n_value}.pdf",
        )

        # F3b: log10(1 + sigma_pi)
        sigma_work = n_df.copy()
        sigma_work["sigma_pi_log10p1"] = sigma_work["sigma_pi"].map(sigma_pi_to_log10p1)
        f3b_agg = _aggregate_metric(sigma_work, "sigma_pi_log10p1")
        f3b_kept = filter_min_support(f3b_agg, support_col="n_valid", min_support=min_support)
        f3b_kept = f3b_kept.sort_values(["config_name", "k_rung"]).reset_index(drop=True)
        f3b_kept.to_csv(
            figdata_outdir / f"F3b_stats_n{n_value}.csv.gz",
            index=False,
            compression="gzip",
        )
        _plot_metric(
            f3b_kept,
            n_value,
            METRIC_LABELS["sigma_pi_log10p1"],
            outdir / f"F3b_n{n_value}.pdf",
        )

        qa[f"n{n_value}"] = {
            "F3a": _build_qa_for_plot(f3a_agg, f3a_kept, rungs, min_support),
            "F3b": _build_qa_for_plot(f3b_agg, f3b_kept, rungs, min_support),
        }

    with open(figdata_outdir / "F3_QA.json", "w", encoding="utf-8") as fh:
        json.dump(qa, fh, indent=2, sort_keys=True)

    print("wrote F3 PDFs, stats CSV.GZ files, and F3_QA.json")
