#!/usr/bin/env python3
"""Shared plotting and rung-policy utilities for paper figures."""

from __future__ import annotations

import math
from typing import Iterable

import pandas as pd

MIN_SUPPORT = 5
CORE_MIN_RUNG = 4
KMAX_CAP = 64


METRIC_LABELS = {
    "x_k_rung": r"resolution rung $k$ (nearest $2^m$ to effective $|X|$)",
    "frob": r"$\|\widehat P(k)-J_{\pi(k)}\|_F$  (A6: Frobenius from rank-1 projector)",
    "sigma_pi_log10p1": r"$\log_{10}(1+\Sigma_{10}(\pi(k)))$  (A6: stationary path-reversal asymmetry)",
    "pla2_gap": r"$\mathrm{PLA2}(\widehat P(k))$  (A6: 2-step least-action dominance gap)",
    "step_entropy": r"$H_{\mathrm{step}}(\widehat P(k))$  (A6: stationary step entropy)",
    "lagr_geo_r2": r"$R^2_{\mathrm{geo}}(\widehat P(k))$  (A6: geometrizability)",
    "lagr_diff_kl": r"$\mathrm{KL}^{\star}_{\mathrm{diff}}(\widehat P(k))$  (A6: diffusion fit KL; lower is better)",
}


def _as_int(value) -> int | None:
    if value is None:
        return None
    try:
        out = int(value)
    except (TypeError, ValueError):
        try:
            out = int(float(value))
        except (TypeError, ValueError):
            return None
    return out


def _as_float(value) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def rungs_for_n(n: int, kmax_cap: int = KMAX_CAP) -> list[int]:
    n_i = _as_int(n)
    if n_i is None or n_i < 2:
        return []
    kmax = min(kmax_cap, n_i // 2)
    out: list[int] = []
    k = 2
    while k <= kmax:
        out.append(k)
        k *= 2
    return out


def map_to_nearest_rung(k_eff: float, rungs: list[int]) -> int | None:
    k_val = _as_float(k_eff)
    if k_val is None or k_val <= 0 or not rungs:
        return None
    log_k = math.log2(k_val)
    best = None
    best_dist = None
    for rung in rungs:
        dist = abs(log_k - math.log2(rung))
        if best is None or dist < best_dist - 1e-15:
            best = rung
            best_dist = dist
        elif abs(dist - best_dist) <= 1e-15 and rung < best:
            best = rung
            best_dist = dist
    return best


def add_rung_columns(df, *, n_col="n", k_eff_col="k_eff") -> pd.DataFrame:
    out = df.copy()
    k_rung_vals: list[float] = []
    k_logdist_vals: list[float] = []
    for n_val, k_eff in zip(out[n_col], out[k_eff_col]):
        rungs = rungs_for_n(_as_int(n_val) or -1)
        k_val = _as_float(k_eff)
        rung = map_to_nearest_rung(k_val if k_val is not None else float("nan"), rungs)
        if rung is None or k_val is None or k_val <= 0:
            k_rung_vals.append(float("nan"))
            k_logdist_vals.append(float("nan"))
            continue
        k_rung_vals.append(float(rung))
        k_logdist_vals.append(abs(math.log2(k_val) - math.log2(rung)))
    out["k_rung"] = k_rung_vals
    out["k_logdist"] = k_logdist_vals
    return out


def dedup_per_run_rung(df, run_cols, rung_col="k_rung", dist_col="k_logdist") -> pd.DataFrame:
    out = df.copy()
    out["_ord"] = range(len(out))
    sort_cols = list(run_cols) + [rung_col, dist_col]
    if "k_eff" in out.columns:
        sort_cols.append("k_eff")
    sort_cols.append("_ord")
    out = out.sort_values(sort_cols, kind="mergesort")
    out = out.drop_duplicates(subset=list(run_cols) + [rung_col], keep="first")
    out = out.drop(columns=["_ord"])
    return out


def filter_min_support(stats_df, support_col="n_valid", min_support: int = MIN_SUPPORT) -> pd.DataFrame:
    out = stats_df.copy()
    return out[out[support_col] >= min_support].copy()


def sigma_pi_to_log10p1(v: float) -> float:
    val = _as_float(v)
    if val is None:
        return float("nan")
    return math.log10(1.0 + max(val, 0.0))
