#!/usr/bin/env python3
"""Generate F7 tau distribution robustness panel for campaign_v3 union."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent))
import plot_common  # required shared plotting module


KEY_CONFIGS = ["empty", "baseline", "full_action", "full_all"]
N_VALUES = [32, 64, 128, 256]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate F7 tau distribution plot and stats.")
    parser.add_argument("--in", dest="in_path", default="paper/figdata/run_summary_table.csv.gz")
    parser.add_argument("--out", default="paper/fig/F7_tau_distribution.pdf")
    parser.add_argument("--stats_out", default="paper/figdata/F7_tau_stats.csv.gz")
    parser.add_argument("--qa_out", default="paper/figdata/F7_QA.json")
    return parser.parse_args()


def _safe_quantile(series: pd.Series, q: float) -> float:
    if series.empty:
        return float("nan")
    return float(series.quantile(q))


def _safe_stat(series: pd.Series, fn: str) -> float:
    if series.empty:
        return float("nan")
    if fn == "median":
        return float(series.median())
    if fn == "min":
        return float(series.min())
    if fn == "max":
        return float(series.max())
    raise ValueError(fn)


def _plot_n_panel(ax, sub: pd.DataFrame, n_value: int, active_ann: dict[str, str]) -> None:
    categories = KEY_CONFIGS
    pos = np.arange(1, len(categories) + 1)

    all_vals: list[float] = []
    for idx, cfg in enumerate(categories, start=1):
        c = sub[sub["config_name"] == cfg].copy()
        vals = c["log10_tau"].dropna().to_numpy(dtype=float)
        if vals.size > 0:
            ax.boxplot(vals, positions=[idx], widths=0.6)
            # Light deterministic jitter for seed-level visibility.
            jitter = np.linspace(-0.08, 0.08, vals.size)
            ax.scatter(np.full(vals.size, idx) + jitter, vals, s=12, alpha=0.55)
            all_vals.extend(vals.tolist())

    if all_vals:
        y_min = float(min(all_vals))
        y_max = float(max(all_vals))
        y_span = max(0.2, y_max - y_min)
        y_pad = 0.15 * y_span
        y_annot = y_max + y_pad
        ax.set_ylim(y_min - 0.12 * y_span, y_max + 0.45 * y_span)
    else:
        y_annot = 0.1
        ax.set_ylim(-0.2, 0.8)

    for idx, cfg in enumerate(categories, start=1):
        ax.text(idx, y_annot, active_ann[cfg], ha="center", va="bottom", fontsize=8)

    ax.set_xticks(pos)
    ax.set_xticklabels(categories, rotation=20)
    ax.set_title(f"n={n_value}")


def main() -> int:
    args = parse_args()

    in_path = Path(args.in_path)
    out_path = Path(args.out)
    stats_path = Path(args.stats_out)
    qa_path = Path(args.qa_out)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    qa_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(in_path)
    df["n"] = pd.to_numeric(df["n"], errors="coerce")
    df = df[df["n"].isin(N_VALUES)].copy()
    df["n"] = df["n"].astype(int)
    df = df[df["config_name"].isin(KEY_CONFIGS)].copy()

    df["tau"] = pd.to_numeric(df["tau"], errors="coerce")
    if "active_tau" in df.columns:
        df["active_tau"] = pd.to_numeric(df["active_tau"], errors="coerce")
    else:
        df["active_tau"] = np.nan

    # log10(tau), only for strictly positive tau.
    df["log10_tau"] = np.where(df["tau"] > 0, np.log10(df["tau"]), np.nan)

    stats_rows = []
    qa = {
        "dataset_id": "campaign_v3_union",
        "n_values": N_VALUES,
        "key_configs": KEY_CONFIGS,
        "group_counts": {},
        "active_tau_annotation": {},
        "key_configs_present": {},
    }

    fig, axes = plt.subplots(1, len(N_VALUES), figsize=(12.8, 4.2), sharey=True)

    for ax, n_value in zip(axes, N_VALUES):
        n_df = df[df["n"] == n_value].copy()

        counts_for_n = {}
        ann_for_n = {}
        missing_cfgs = []

        for cfg in KEY_CONFIGS:
            c = n_df[n_df["config_name"] == cfg].copy()
            run_count = int(len(c))
            counts_for_n[cfg] = run_count
            if run_count == 0:
                missing_cfgs.append(cfg)

            tau_defined = c["tau"].dropna()
            active_defined = int(c["active_tau"].notna().sum())
            active_rate = float(active_defined / run_count) if run_count > 0 else float("nan")
            ann_for_n[cfg] = f"{active_defined}/{run_count}"

            stats_rows.append(
                {
                    "n": n_value,
                    "config_name": cfg,
                    "count": run_count,
                    "tau_median": _safe_stat(tau_defined, "median"),
                    "tau_q25": _safe_quantile(tau_defined, 0.25),
                    "tau_q75": _safe_quantile(tau_defined, 0.75),
                    "tau_min": _safe_stat(tau_defined, "min"),
                    "tau_max": _safe_stat(tau_defined, "max"),
                    "active_tau_defined_count": active_defined,
                    "active_tau_defined_rate": active_rate,
                }
            )

        qa["group_counts"][str(n_value)] = counts_for_n
        qa["active_tau_annotation"][str(n_value)] = ann_for_n
        qa["key_configs_present"][str(n_value)] = {
            "all_present": len(missing_cfgs) == 0,
            "missing": missing_cfgs,
        }

        _plot_n_panel(ax, n_df, n_value, ann_for_n)

    axes[0].set_ylabel(r"$\log_{10}(\tau)$")
    for ax in axes:
        ax.set_xlabel("config")
    fig.suptitle("campaign_v3 tau policy outcomes by n", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(out_path)
    plt.close(fig)

    stats_df = pd.DataFrame(stats_rows)
    stats_df = stats_df.sort_values(["n", "config_name"]).reset_index(drop=True)
    stats_df.to_csv(stats_path, index=False, compression="gzip")

    with open(qa_path, "w", encoding="utf-8") as fh:
        json.dump(qa, fh, indent=2, sort_keys=True)

    print(f"wrote={out_path}")
    print(f"wrote={stats_path}")
    print(f"wrote={qa_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
