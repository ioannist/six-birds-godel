#!/usr/bin/env python3
"""Generate F8 robustness panels: sigma_ratio distribution + REV frequency heatmap."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent))
from plot_common import sigma_pi_to_log10p1


KEY_CONFIGS = ["empty", "baseline", "full_action", "full_all"]
N_VALUES = [32, 64, 128, 256]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate F8 sigma_ratio and REV robustness plots.")
    parser.add_argument("--in", dest="in_path", default="paper/figdata/run_summary_table.csv.gz")
    parser.add_argument("--out_sigma", default="paper/fig/F8_sigma_ratio_distribution.pdf")
    parser.add_argument("--out_rev", default="paper/fig/F8_REV_frequency_heatmap.pdf")
    parser.add_argument("--stats_sigma", default="paper/figdata/F8_sigma_ratio_stats.csv.gz")
    parser.add_argument("--stats_rev", default="paper/figdata/F8_REV_stats.csv.gz")
    parser.add_argument("--qa_out", default="paper/figdata/F8_QA.json")
    return parser.parse_args()


def _to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "t", "1", "yes", "y"}:
        return True
    if text in {"false", "f", "0", "no", "n", ""}:
        return False
    return False


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


def _plot_sigma_panel(ax, n_df: pd.DataFrame, n_value: int, ann: dict[str, str]) -> None:
    pos = np.arange(1, len(KEY_CONFIGS) + 1)
    all_vals: list[float] = []

    for idx, cfg in enumerate(KEY_CONFIGS, start=1):
        c = n_df[n_df["config_name"] == cfg].copy()
        vals = c["sigma_ratio_log10p1"].dropna().to_numpy(dtype=float)
        if vals.size >= 2:
            ax.boxplot(vals, positions=[idx], widths=0.6)
        elif vals.size == 1:
            ax.scatter([idx], vals, s=20)
        if vals.size > 0:
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

    for idx, cfg in enumerate(KEY_CONFIGS, start=1):
        ax.text(idx, y_annot, ann[cfg], ha="center", va="bottom", fontsize=8)

    ax.set_xticks(pos)
    ax.set_xticklabels(KEY_CONFIGS, rotation=20)
    ax.set_title(f"n={n_value}")


def _plot_rev_heatmap(out_path: Path, rev_stats: pd.DataFrame, include_configs: list[str]) -> None:
    pivot = (
        rev_stats[rev_stats["config_name"].isin(include_configs)]
        .pivot(index="config_name", columns="n", values="rev_rate")
        .reindex(index=include_configs, columns=N_VALUES)
    )

    mat = pivot.to_numpy(dtype=float)
    finite_vals = mat[np.isfinite(mat)]
    vmax = float(finite_vals.max()) if finite_vals.size > 0 and finite_vals.max() > 0 else 1.0

    fig_h = max(4.2, 0.26 * len(include_configs) + 1.3)
    plt.figure(figsize=(7.0, fig_h))
    im = plt.imshow(mat, aspect="auto", cmap="viridis", vmin=0.0, vmax=vmax)
    plt.colorbar(im, label="REV rate")
    plt.xticks(range(len(N_VALUES)), N_VALUES)
    plt.yticks(range(len(include_configs)), include_configs)
    plt.xlabel("n")
    plt.ylabel("config")
    plt.title("campaign_v3 REV frequency heatmap")

    for i, cfg in enumerate(include_configs):
        for j, n_value in enumerate(N_VALUES):
            val = mat[i, j]
            label = "NA" if not np.isfinite(val) else f"{val:.2f}"
            # White text on dark cells, black on bright cells
            norm_val = val / vmax if (np.isfinite(val) and vmax > 0) else 0.0
            txt_color = "white" if norm_val < 0.55 else "black"
            plt.text(j, i, label, ha="center", va="center", fontsize=7, color=txt_color)

    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, bbox_inches="tight")
    plt.close()


def main() -> int:
    args = parse_args()

    in_path = Path(args.in_path)
    out_sigma = Path(args.out_sigma)
    out_rev = Path(args.out_rev)
    stats_sigma = Path(args.stats_sigma)
    stats_rev = Path(args.stats_rev)
    qa_out = Path(args.qa_out)

    out_sigma.parent.mkdir(parents=True, exist_ok=True)
    out_rev.parent.mkdir(parents=True, exist_ok=True)
    stats_sigma.parent.mkdir(parents=True, exist_ok=True)
    stats_rev.parent.mkdir(parents=True, exist_ok=True)
    qa_out.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(in_path)
    df["n"] = pd.to_numeric(df["n"], errors="coerce")
    df = df[df["n"].isin(N_VALUES)].copy()
    df["n"] = df["n"].astype(int)

    df["sigma_ratio"] = pd.to_numeric(df["sigma_ratio"], errors="coerce")
    df["sigma_ratio_log10p1"] = df["sigma_ratio"].map(sigma_pi_to_log10p1)
    df["is_REV_bool"] = df["is_REV"].map(_to_bool)

    # Sigma ratio distribution stats/plot for key configs.
    key_df = df[df["config_name"].isin(KEY_CONFIGS)].copy()
    sigma_rows = []
    missing_table = {}
    low_defined_groups = []

    fig, axes = plt.subplots(1, len(N_VALUES), figsize=(12.8, 4.2), sharey=True)
    for ax, n_value in zip(axes, N_VALUES):
        n_df = key_df[key_df["n"] == n_value].copy()
        ann_for_n = {}
        missing_table[str(n_value)] = {}

        for cfg in KEY_CONFIGS:
            c = n_df[n_df["config_name"] == cfg].copy()
            run_count = int(len(c))
            defined = c["sigma_ratio_log10p1"].dropna()
            defined_count = int(len(defined))
            missing_count = int(run_count - defined_count)
            missing_rate = float(missing_count / run_count) if run_count > 0 else float("nan")

            if defined_count < 2:
                low_defined_groups.append(
                    {
                        "n": n_value,
                        "config_name": cfg,
                        "defined_count": defined_count,
                        "run_count": run_count,
                    }
                )

            ann_for_n[cfg] = f"{defined_count}/{run_count}"
            missing_table[str(n_value)][cfg] = {
                "defined_count": defined_count,
                "missing_count": missing_count,
                "missing_rate": missing_rate,
            }

            sigma_rows.append(
                {
                    "n": n_value,
                    "config_name": cfg,
                    "defined_count": defined_count,
                    "missing_count": missing_count,
                    "missing_rate": missing_rate,
                    "median_log10p1": _safe_stat(defined, "median"),
                    "q25_log10p1": _safe_quantile(defined, 0.25),
                    "q75_log10p1": _safe_quantile(defined, 0.75),
                    "min_log10p1": _safe_stat(defined, "min"),
                    "max_log10p1": _safe_stat(defined, "max"),
                }
            )

        _plot_sigma_panel(ax, n_df, n_value, ann_for_n)

    axes[0].set_ylabel(r"$\log_{10}(1+\mathrm{sigma\_ratio})$")
    for ax in axes:
        ax.set_xlabel("config")
    fig.suptitle("campaign_v3: sigma_ratio retention proxy", fontsize=11)
    fig.subplots_adjust(left=0.06, right=0.99, bottom=0.21, top=0.82, wspace=0.22)
    fig.savefig(out_sigma)
    plt.close(fig)

    sigma_df = pd.DataFrame(sigma_rows).sort_values(["n", "config_name"]).reset_index(drop=True)
    sigma_df.to_csv(stats_sigma, index=False, compression="gzip")

    # REV stats/heatmap across selected configs.
    rev_stats = (
        df.groupby(["config_name", "n"], as_index=False)
        .agg(rev_count=("is_REV_bool", "sum"), run_count=("is_REV_bool", "size"))
    )
    rev_stats["rev_count"] = rev_stats["rev_count"].astype(int)
    rev_stats["run_count"] = rev_stats["run_count"].astype(int)
    rev_stats["rev_rate"] = rev_stats["rev_count"] / rev_stats["run_count"].where(rev_stats["run_count"] > 0, np.nan)

    configs_with_rev = set(
        rev_stats.groupby("config_name")["rev_rate"].max().loc[lambda s: s > 0].index.tolist()
    )
    include_configs = sorted(set(KEY_CONFIGS) | configs_with_rev)

    order_df = (
        rev_stats[rev_stats["config_name"].isin(include_configs)]
        .groupby("config_name", as_index=False)
        .agg(max_rev_rate=("rev_rate", "max"))
        .sort_values(["max_rev_rate", "config_name"], ascending=[False, True])
    )
    include_configs = order_df["config_name"].tolist()

    rev_complete_idx = pd.MultiIndex.from_product([include_configs, N_VALUES], names=["config_name", "n"])
    rev_complete = (
        rev_stats.set_index(["config_name", "n"])
        .reindex(rev_complete_idx)
        .reset_index()
    )
    rev_complete["rev_count"] = pd.to_numeric(rev_complete["rev_count"], errors="coerce").fillna(0).astype(int)
    rev_complete["run_count"] = pd.to_numeric(rev_complete["run_count"], errors="coerce").fillna(0).astype(int)
    rev_complete["rev_rate"] = np.where(
        rev_complete["run_count"] > 0,
        rev_complete["rev_count"] / rev_complete["run_count"],
        np.nan,
    )

    rev_complete.to_csv(stats_rev, index=False, compression="gzip")
    _plot_rev_heatmap(out_rev, rev_complete, include_configs)

    # QA.
    total_missing = int((~np.isfinite(key_df["sigma_ratio"])).sum())
    total_key = int(len(key_df))
    global_missing_rate = float(total_missing / total_key) if total_key > 0 else float("nan")

    rev_totals_by_n = {}
    for n_value in N_VALUES:
        n_rev = rev_complete[rev_complete["n"] == n_value]
        rev_totals_by_n[str(n_value)] = {
            "rev_count": int(n_rev["rev_count"].sum()),
            "run_count": int(n_rev["run_count"].sum()),
        }

    qa = {
        "dataset_id": "campaign_v3_union",
        "n_values": N_VALUES,
        "key_configs": KEY_CONFIGS,
        "sigma_ratio_missingness": missing_table,
        "global_missingness_rate_key_configs": global_missing_rate,
        "groups_defined_count_lt2": low_defined_groups,
        "rev_totals_by_n": rev_totals_by_n,
        "rev_heatmap_configs": include_configs,
    }

    with open(qa_out, "w", encoding="utf-8") as fh:
        json.dump(qa, fh, indent=2, sort_keys=True)

    print(f"wrote={out_sigma}")
    print(f"wrote={out_rev}")
    print(f"wrote={stats_sigma}")
    print(f"wrote={stats_rev}")
    print(f"wrote={qa_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
