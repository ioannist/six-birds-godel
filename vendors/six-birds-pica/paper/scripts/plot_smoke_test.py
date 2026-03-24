#!/usr/bin/env python3
"""Minimal smoke plot to validate plot_common integration."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent))
from plot_common import METRIC_LABELS, MIN_SUPPORT, filter_min_support


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a smoke-test frob vs rung plot.")
    parser.add_argument(
        "--input",
        default="paper/figdata/scan_rung_table.csv.gz",
        help="Input scan table path.",
    )
    parser.add_argument(
        "--out",
        default="paper/fig/SMOKE_frob_n128.pdf",
        help="Output PDF path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    df = pd.read_csv(args.input)
    keep_configs = ["empty", "baseline", "full_action", "full_all"]
    sub = df[
        (df["exp_id"] == "EXP-112")
        & (df["n"] == 128)
        & (df["config_name"].isin(keep_configs))
    ].copy()

    sub["frob"] = pd.to_numeric(sub["frob"], errors="coerce")
    sub["k_rung"] = pd.to_numeric(sub["k_rung"], errors="coerce")

    grouped = (
        sub.groupby(["config_name", "k_rung"], as_index=False)
        .agg(
            median=("frob", "median"),
            q25=("frob", lambda s: s.quantile(0.25)),
            q75=("frob", lambda s: s.quantile(0.75)),
            n_valid=("frob", lambda s: int(s.notna().sum())),
        )
    )

    grouped = filter_min_support(grouped, support_col="n_valid", min_support=MIN_SUPPORT)
    if grouped.empty:
        raise SystemExit("No rows remain after filtering for minimum support.")

    plt.figure(figsize=(7, 4.5))
    for config_name, g in grouped.groupby("config_name", sort=True):
        g = g.sort_values("k_rung")
        y = g["median"].to_numpy()
        yerr_lower = (g["median"] - g["q25"]).to_numpy()
        yerr_upper = (g["q75"] - g["median"]).to_numpy()
        plt.errorbar(
            g["k_rung"].to_numpy(),
            y,
            yerr=[yerr_lower, yerr_upper],
            marker="o",
            capsize=3,
            label=config_name,
        )

    plt.xlabel(METRIC_LABELS["x_k_rung"])
    plt.ylabel(METRIC_LABELS["frob"])
    plt.title("SMOKE: EXP-112 n=128 frob by rung")
    plt.legend()
    plt.tight_layout()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path)
    plt.close()
    print(f"wrote={out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
