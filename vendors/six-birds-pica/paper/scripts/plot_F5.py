#!/usr/bin/env python3
"""Generate F5 regime separation scatter by n (multi-exp at n=256)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.path.append(str(Path(__file__).resolve().parent))
from plot_common import sigma_pi_to_log10p1


HIGHLIGHT_CONFIGS = ["baseline", "full_action", "full_all"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate F5 regime scatter.")
    parser.add_argument("--in", dest="in_path", default="paper/figdata/run_summary_table.csv.gz")
    parser.add_argument("--out", default="paper/fig/F5_regime_scatter_n128.pdf")
    parser.add_argument("--figdata_out", default="paper/figdata/F5_points_n128.csv.gz")
    parser.add_argument("--qa_out", default="paper/figdata/F5_QA.json")
    parser.add_argument("--n", type=int, default=128)
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


def _centroid(df: pd.DataFrame, cfg: str):
    c = df[df["config_name"] == cfg]
    if c.empty:
        return None
    return {
        "x": float(c["tilde_geo_r2"].median()),
        "y": float(c["y_log10p1"].median()),
    }


if __name__ == "__main__":
    args = parse_args()

    in_path = Path(args.in_path)
    out_path = Path(args.out)
    figdata_out = Path(args.figdata_out)
    qa_out = Path(args.qa_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    figdata_out.parent.mkdir(parents=True, exist_ok=True)
    qa_out.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(in_path)
    df = df[pd.to_numeric(df["n"], errors="coerce") == args.n].copy()
    rows_total = int(len(df))

    rev_mask = df["is_REV"].map(_to_bool)
    rows_excluded_rev = int(rev_mask.sum())
    non_rev = df[~rev_mask].copy()

    non_rev["tilde_geo_r2"] = pd.to_numeric(non_rev["tilde_geo_r2"], errors="coerce")
    non_rev["tilde_sigma_pi"] = pd.to_numeric(non_rev["tilde_sigma_pi"], errors="coerce")
    non_rev["y_log10p1"] = non_rev["tilde_sigma_pi"].map(sigma_pi_to_log10p1)

    finite_mask = np.isfinite(non_rev["tilde_geo_r2"]) & np.isfinite(non_rev["y_log10p1"])
    rows_excluded_nan = int((~finite_mask).sum())
    plotted = non_rev[finite_mask].copy()
    rows_plotted = int(len(plotted))

    plotted_out_cols = [
        "exp_id",
        "config_name",
        "n",
        "seed",
        "tau",
        "active_tau",
        "log_file",
        "tilde_geo_r2",
        "tilde_sigma_pi",
        "y_log10p1",
        "is_REV",
    ]
    existing_cols = [c for c in plotted_out_cols if c in plotted.columns]
    plotted[existing_cols].to_csv(figdata_out, index=False, compression="gzip")

    plt.figure(figsize=(7.2, 4.8))
    for cfg, grp in plotted.groupby("config_name", sort=True):
        plt.scatter(grp["tilde_geo_r2"], grp["y_log10p1"], s=26, alpha=0.85)

    centroid_payload = {}
    for cfg in HIGHLIGHT_CONFIGS:
        cent = _centroid(plotted, cfg)
        centroid_payload[f"{cfg}_centroid"] = cent
        if cent is None:
            continue
        plt.scatter(
            [cent["x"]],
            [cent["y"]],
            s=120,
            facecolors="none",
            edgecolors="black",
            linewidths=1.4,
            zorder=5,
        )
        plt.text(cent["x"], cent["y"], f" {cfg}", fontsize=9, va="center")

    plt.xlabel(
        r"$\widetilde{R^2_{\mathrm{geo}}}$  (median over rungs $k\geq4$ of $R^2_{\mathrm{geo}}(\widehat P(k))$)"
    )
    plt.ylabel(
        r"$\log_{10}(1+\widetilde{\Sigma}_{10}(\pi))$  (median over rungs $k\geq4$ of $\Sigma_{10}(\pi(k))$)"
    )
    plt.title(f"n={args.n} regime scatter (REV excluded)")
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()

    counts_by_exp_id = {
        str(k): int(v) for k, v in df["exp_id"].value_counts(dropna=False).sort_index().items()
    }
    qa_entry = {
        "n": args.n,
        "rows_total": rows_total,
        "rows_excluded_REV": rows_excluded_rev,
        "rows_excluded_nan": rows_excluded_nan,
        "rows_plotted": rows_plotted,
        "unique_configs_plotted": int(plotted["config_name"].nunique()),
        "configs_plotted": sorted(plotted["config_name"].dropna().unique().tolist()),
        "exp_ids_present": sorted(df["exp_id"].dropna().astype(str).unique().tolist()),
        "counts_by_exp_id": counts_by_exp_id,
    }
    qa_entry.update(centroid_payload)

    if qa_out.exists():
        with open(qa_out, "r", encoding="utf-8") as fh:
            loaded = json.load(fh)
            if isinstance(loaded, dict):
                qa_all = {
                    k: v
                    for k, v in loaded.items()
                    if isinstance(k, str) and k.startswith("n") and isinstance(v, dict)
                }
            else:
                qa_all = {}
    else:
        qa_all = {}
    qa_all[f"n{args.n}"] = qa_entry

    with open(qa_out, "w", encoding="utf-8") as fh:
        json.dump(qa_all, fh, indent=2, sort_keys=True)

    print(f"wrote={out_path}")
    print(f"wrote={figdata_out}")
    print(f"wrote={qa_out}")
