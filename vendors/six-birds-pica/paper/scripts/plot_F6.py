#!/usr/bin/env python3
"""Generate F6 leave-one-out ablation heatmap with n<=128 pooled and n=256 targeted panels."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent))
import plot_common  # noqa: F401  # required shared import for policy consistency


TOKEN = "KEY_AUDIT_JSON"
EPS = 1e-15
N_VALUES_CORE = [32, 64, 128]

METRICS = [
    ("tilde_pla2_gap", r"$ES_{\mathrm{MAD}}(\widetilde{\mathrm{PLA2}})$"),
    ("tilde_geo_r2", r"$ES_{\mathrm{MAD}}(\widetilde{R^2_{\mathrm{geo}}})$"),
    ("tilde_sigma_pi", r"$ES_{\mathrm{MAD}}(\widetilde{\Sigma}_{10}(\pi))$"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate F6 LOO ablation heatmap.")
    parser.add_argument("--run_summary", default="paper/figdata/run_summary_table.csv.gz")
    parser.add_argument("--log_glob", default="lab/runs/campaign_v3/wave_3/wave_3/*.log")  # compatibility only
    parser.add_argument("--out", default="paper/fig/F6_LOO_heatmap.pdf")
    parser.add_argument("--loo_map_out", default="paper/figdata/loo_cell_map.csv")
    parser.add_argument("--matrix_out", default="paper/figdata/F6_heatmap_matrix.csv.gz")
    parser.add_argument("--qa_out", default="paper/figdata/F6_QA.json")
    parser.add_argument("--exp", default="EXP-112")
    return parser.parse_args()


def _to_float(v):
    try:
        out = float(v)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def _mad(vals: np.ndarray) -> float:
    med = float(np.median(vals))
    return float(np.median(np.abs(vals - med)))


def _es_mad(x: np.ndarray, y: np.ndarray) -> float:
    mx = float(np.median(x))
    my = float(np.median(y))
    madx = _mad(x)
    mady = _mad(y)
    return (mx - my) / (0.5 * (madx + mady) + EPS)


def _extract_key_audit_jsons(text: str) -> List[Tuple[dict, int]]:
    out: List[Tuple[dict, int]] = []
    i = 0
    n = len(text)
    while i < n:
        idx = text.find(TOKEN, i)
        if idx < 0:
            break
        j = idx + len(TOKEN)
        while j < n and text[j] != "{":
            j += 1
        if j >= n:
            break

        start = j
        depth = 0
        in_string = False
        escaped = False
        end = None
        for pos in range(start, n):
            ch = text[pos]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
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
                out.append((obj, start))
        except json.JSONDecodeError:
            pass
        i = end
    return out


def _step_rank(obj: dict) -> float:
    s = _to_float(obj.get("step"))
    if s is not None:
        return s
    t = _to_float(obj.get("t"))
    return t if t is not None else float("-inf")


def _matrix_from_audit(obj: dict):
    pica_cfg = obj.get("pica_config")
    if not isinstance(pica_cfg, dict):
        return None
    enabled = pica_cfg.get("enabled")
    if not isinstance(enabled, list) or len(enabled) != 6:
        return None
    mat = []
    for row in enabled:
        if not isinstance(row, list) or len(row) != 6:
            return None
        mat.append([bool(x) for x in row])
    return mat


def _read_matrix_from_log(log_path: str):
    p = Path(log_path)
    if not p.exists():
        return None
    text = p.read_text(encoding="utf-8", errors="replace")
    payloads = _extract_key_audit_jsons(text)
    if not payloads:
        return None
    best_obj, _ = max(payloads, key=lambda x: (_step_rank(x[0]), x[1]))
    return _matrix_from_audit(best_obj)


def _select_rep_logs(run_df: pd.DataFrame, n_value: int, configs: List[str]) -> Dict[str, str]:
    sub = run_df[(run_df["n"] == n_value) & (run_df["config_name"].isin(configs))].copy()
    sub = sub[sub["log_file"].notna()].copy()
    reps: Dict[str, str] = {}
    for cfg, grp in sub.groupby("config_name"):
        paths = sorted(str(x) for x in grp["log_file"].tolist() if isinstance(x, str) and x)
        if paths:
            reps[str(cfg)] = paths[0]
    return reps


def _loo_diff(full_mat, loo_mat):
    removed = []
    added = []
    for i in range(6):
        for j in range(6):
            f = bool(full_mat[i][j])
            l = bool(loo_mat[i][j])
            if f and not l:
                removed.append((i, j))
            elif (not f) and l:
                added.append((i, j))
    return removed, added


def _series_vals(run: pd.DataFrame, cfg: str, n_value: int, metric: str) -> np.ndarray:
    s = pd.to_numeric(run[(run["config_name"] == cfg) & (run["n"] == n_value)][metric], errors="coerce")
    vals = s.to_numpy(dtype=float)
    return vals[np.isfinite(vals)]


def _metric_summary(mat: np.ndarray) -> dict:
    out = {}
    for i, (metric, _) in enumerate(METRICS):
        vals = mat[i, :]
        vals = vals[np.isfinite(vals)]
        if vals.size == 0:
            out[metric] = {"min": None, "median": None, "max": None}
        else:
            out[metric] = {
                "min": float(np.min(vals)),
                "median": float(np.median(vals)),
                "max": float(np.max(vals)),
            }
    return out


def main() -> int:
    args = parse_args()

    out_path = Path(args.out)
    loo_map_out = Path(args.loo_map_out)
    matrix_out = Path(args.matrix_out)
    qa_out = Path(args.qa_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    loo_map_out.parent.mkdir(parents=True, exist_ok=True)
    matrix_out.parent.mkdir(parents=True, exist_ok=True)
    qa_out.parent.mkdir(parents=True, exist_ok=True)

    run = pd.read_csv(args.run_summary)
    run["n"] = pd.to_numeric(run["n"], errors="coerce")
    run = run[np.isfinite(run["n"])].copy()
    run["n"] = run["n"].astype(int)

    all_loo_configs = sorted(c for c in run["config_name"].dropna().unique().tolist() if str(c).startswith("loo_"))

    # Context 1: canonical mapping from n=128 representatives.
    rep128 = _select_rep_logs(run, 128, ["full_action"] + all_loo_configs)
    if "full_action" not in rep128:
        raise SystemExit("Missing n=128 full_action representative log in run_summary_table.")
    full128 = _read_matrix_from_log(rep128["full_action"])
    if full128 is None:
        raise SystemExit(f"Failed to parse pica_config.enabled from {rep128['full_action']}")

    map_rows = []
    valid_rows = []
    anomalies = []
    canonical_cell_by_cfg: Dict[str, str] = {}

    for cfg in all_loo_configs:
        row = {"config_name": cfg, "actor": "", "informant": "", "cell_label": ""}
        rep = rep128.get(cfg)
        if rep is None:
            anomalies.append({"config_name": cfg, "removed_count": None, "added_count": None, "reason": "missing_n128_representative"})
            map_rows.append(row)
            continue
        loo_mat = _read_matrix_from_log(rep)
        if loo_mat is None:
            anomalies.append({"config_name": cfg, "removed_count": None, "added_count": None, "reason": f"failed_parse:{rep}"})
            map_rows.append(row)
            continue
        removed, added = _loo_diff(full128, loo_mat)
        if len(removed) == 1 and len(added) == 0:
            i, j = removed[0]
            label = f"P{i+1}←P{j+1}"
            row.update({"actor": i + 1, "informant": j + 1, "cell_label": label})
            valid_rows.append({"config_name": cfg, "actor": i + 1, "informant": j + 1, "cell_label": label})
            canonical_cell_by_cfg[cfg] = label
        else:
            anomalies.append({"config_name": cfg, "removed_count": len(removed), "added_count": len(added), "reason": "not_single_removal"})
        map_rows.append(row)

    map_df = pd.DataFrame(map_rows).sort_values("config_name")
    map_df.to_csv(loo_map_out, index=False)

    valid_rows = sorted(valid_rows, key=lambda r: (r["actor"], r["informant"], r["config_name"]))
    columns_core = [r["cell_label"] for r in valid_rows]
    core_cfg_order = [r["config_name"] for r in valid_rows]

    # Core pooled (n=32/64/128) + n256 ES on canonical columns.
    matrix_core = np.full((len(METRICS), len(core_cfg_order)), np.nan, dtype=float)
    es256_by_cfg_metric: Dict[Tuple[str, str], float] = {}
    long_rows = []

    for c_idx, c_meta in enumerate(valid_rows):
        cfg = c_meta["config_name"]
        for r_idx, (metric, metric_label) in enumerate(METRICS):
            es_core = []
            for n_val in N_VALUES_CORE:
                x = _series_vals(run, cfg, n_val, metric)
                y = _series_vals(run, "full_action", n_val, metric)
                if x.size == 0 or y.size == 0:
                    es_core.append(np.nan)
                else:
                    es_core.append(_es_mad(x, y))

            x256 = _series_vals(run, cfg, 256, metric)
            y256 = _series_vals(run, "full_action", 256, metric)
            es256 = _es_mad(x256, y256) if (x256.size > 0 and y256.size > 0) else np.nan
            es256_by_cfg_metric[(cfg, metric)] = es256

            finite = [v for v in es_core if np.isfinite(v)]
            pooled = float(np.median(finite)) if finite else np.nan
            matrix_core[r_idx, c_idx] = pooled

            long_rows.append(
                {
                    "metric_key": metric,
                    "metric_label": metric_label,
                    "config_name": cfg,
                    "actor": c_meta["actor"],
                    "informant": c_meta["informant"],
                    "cell_label": c_meta["cell_label"],
                    "es_n32": es_core[0],
                    "es_n64": es_core[1],
                    "es_n128": es_core[2],
                    "pooled_es_mad": pooled,
                    "es_n256": es256,
                }
            )

    # Context 2: n=256 targeted subset verification and panel data.
    present_loo_256 = sorted(c for c in run[run["n"] == 256]["config_name"].dropna().unique().tolist() if str(c).startswith("loo_"))
    rep256 = _select_rep_logs(run, 256, ["full_action"] + present_loo_256)
    n256_mismatches = []

    full256 = None
    if "full_action" in rep256:
        full256 = _read_matrix_from_log(rep256["full_action"])

    panel256_cfgs = []
    for cfg in present_loo_256:
        if full256 is None:
            n256_mismatches.append({"config_name": cfg, "reason": "missing_n256_full_action"})
            continue
        rep = rep256.get(cfg)
        if rep is None:
            n256_mismatches.append({"config_name": cfg, "reason": "missing_n256_representative"})
            continue
        loo_mat = _read_matrix_from_log(rep)
        if loo_mat is None:
            n256_mismatches.append({"config_name": cfg, "reason": f"failed_parse:{rep}"})
            continue
        removed, added = _loo_diff(full256, loo_mat)
        if len(removed) != 1 or len(added) != 0:
            n256_mismatches.append({"config_name": cfg, "reason": "not_single_removal", "removed_count": len(removed), "added_count": len(added)})
            continue
        i, j = removed[0]
        label256 = f"P{i+1}←P{j+1}"
        canonical_label = canonical_cell_by_cfg.get(cfg)
        if canonical_label is None:
            n256_mismatches.append({"config_name": cfg, "reason": "not_in_canonical_loo_set", "label_n256": label256})
            continue
        if canonical_label != label256:
            n256_mismatches.append({"config_name": cfg, "reason": "label_mismatch_vs_n128", "label_n128": canonical_label, "label_n256": label256})
            continue
        panel256_cfgs.append(cfg)

    panel256_cfgs = sorted(panel256_cfgs, key=lambda c: (int(next(r["actor"] for r in valid_rows if r["config_name"] == c)), int(next(r["informant"] for r in valid_rows if r["config_name"] == c)), c))
    columns_256 = [canonical_cell_by_cfg[c] for c in panel256_cfgs]
    matrix_256 = np.full((len(METRICS), max(1, len(panel256_cfgs))), np.nan, dtype=float)
    if panel256_cfgs:
        for c_idx, cfg in enumerate(panel256_cfgs):
            for r_idx, (metric, _) in enumerate(METRICS):
                matrix_256[r_idx, c_idx] = es256_by_cfg_metric.get((cfg, metric), np.nan)

    # Save long matrix data with es_n256.
    matrix_long_df = pd.DataFrame(long_rows)
    matrix_long_df = matrix_long_df.sort_values(["actor", "informant", "config_name", "metric_key"]).reset_index(drop=True)
    matrix_long_df.to_csv(matrix_out, index=False, compression="gzip")

    # Two-panel heatmap with shared color scale.
    vals_all = []
    vals_all.extend(matrix_core[np.isfinite(matrix_core)].tolist())
    if panel256_cfgs:
        vals_all.extend(matrix_256[np.isfinite(matrix_256)].tolist())
    vmax = float(np.max(np.abs(vals_all))) if vals_all else 1.0
    if vmax <= 0:
        vmax = 1.0

    width_left = max(6.8, 0.36 * max(1, len(columns_core)))
    width_right = max(3.0, 0.45 * max(1, len(columns_256)))
    fig, (ax0, ax1) = plt.subplots(
        1,
        2,
        figsize=(width_left + width_right, 4.3),
        gridspec_kw={"width_ratios": [max(1, len(columns_core)), max(1, len(columns_256))]},
        sharey=True,
    )

    im0 = ax0.imshow(np.ma.masked_invalid(matrix_core), aspect="auto", cmap="gray", vmin=-vmax, vmax=vmax)
    ax0.set_xticks(np.arange(len(columns_core)))
    ax0.set_xticklabels(columns_core, rotation=90)
    ax0.set_yticks(np.arange(len(METRICS)))
    ax0.set_yticklabels([m[1] for m in METRICS])
    ax0.set_title("(a) Pooled LOO (median ES_MAD over n=32/64/128)")

    im1 = ax1.imshow(np.ma.masked_invalid(matrix_256), aspect="auto", cmap="gray", vmin=-vmax, vmax=vmax)
    ax1.set_xticks(np.arange(len(columns_256)))
    ax1.set_xticklabels(columns_256, rotation=90)
    ax1.set_title("(b) n=256 targeted LOO subset")

    cbar = fig.colorbar(im1, ax=[ax0, ax1], fraction=0.03, pad=0.02)
    cbar.set_label(r"$ES_{\mathrm{MAD}}$ (loo − full_action)")

    fig.suptitle(
        "Leave-one-out ablations\n"
        "metrics = medians over rungs $k\\geq4$",
        y=1.03,
    )
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)

    metric_summary_core = _metric_summary(matrix_core)
    metric_summary_n256 = _metric_summary(matrix_256[:, : len(panel256_cfgs)] if panel256_cfgs else np.full((len(METRICS), 0), np.nan))

    missing_loo_256 = sorted(set(core_cfg_order) - set(present_loo_256))
    qa = {
        "exp_id": args.exp,
        "loo_configs_total": len(all_loo_configs),
        "loo_configs_valid_single_removal": len(valid_rows),
        "loo_configs_with_anomalies": len(anomalies),
        "anomalies": anomalies,
        "removed_cells_unique_count": len(set(columns_core)),
        "columns_sorted_by": "actor_then_informant",
        "metric_pooled_es_summary": metric_summary_core,
        "valid_single_removal_summary": f"valid_single_removal = {len(valid_rows)} / {len(all_loo_configs)}",
        "n256_present_loo_configs": present_loo_256,
        "n256_missing_loo_configs": missing_loo_256,
        "n256_missing_loo_configs_count": len(missing_loo_256),
        "n256_panel_loo_configs": panel256_cfgs,
        "n256_panel_cell_labels": columns_256,
        "n256_matrix_mismatch_count": len(n256_mismatches),
        "n256_matrix_mismatches": n256_mismatches,
        "metric_n256_es_summary": metric_summary_n256,
    }
    qa_out.write_text(json.dumps(qa, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"valid_single_removal = {len(valid_rows)} / {len(all_loo_configs)}")
    print(f"wrote={out_path}")
    print(f"wrote={loo_map_out}")
    print(f"wrote={matrix_out}")
    print(f"wrote={qa_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
