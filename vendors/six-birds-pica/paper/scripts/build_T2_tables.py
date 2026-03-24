#!/usr/bin/env python3
"""Build T2A/T2B/T2C tables for campaign_v3 manifest-driven paper dataset."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd


TOKEN = "KEY_AUDIT_JSON"
KEY_CONFIGS = ["empty", "baseline", "full_action", "full_all", "gen6_core_A12_A25"]
SHORT_LABELS = {
    "empty": "Null",
    "baseline": "Baseline",
    "full_action": "Full-Action",
    "full_all": "Full-All",
    "gen6_core_A12_A25": "Gen6-core",
}
WAVE2_EXP_ORDER = ["EXP-F1", "EXP-100", "EXP-101", "EXP-106", "EXP-107", "EXP-109", "EXP-110", "EXP-112"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build T2 tables + QA for manifest-driven figdata.")
    p.add_argument("--run_summary", default="paper/figdata/run_summary_table.csv.gz")
    p.add_argument("--manifest", default="paper/figdata/paper_dataset_manifest.json")
    p.add_argument("--wave2_dir", default="lab/runs/campaign_v3/wave_2/wave_2")
    p.add_argument("--wave2_audits", default="lab/runs/campaign_v3/wave_2/audits.jsonl")
    p.add_argument("--wave2_manifest", default="lab/runs/campaign_v3/wave_2/manifest.json")
    p.add_argument("--out_tables", default="paper/tables")
    p.add_argument("--out_figdata", default="paper/figdata")
    p.add_argument("--qa_out", default="paper/figdata/T2_QA.json")
    p.add_argument("--force", action="store_true")
    return p.parse_args()


def to_bool(v: object) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    if isinstance(v, (int, float)):
        return bool(v)
    s = str(v).strip().lower()
    return s in {"1", "true", "t", "yes", "y"}


def to_int(v: object) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        if not math.isfinite(v):
            return None
        return int(v)
    if isinstance(v, str):
        try:
            return int(float(v))
        except ValueError:
            return None
    return None


def to_float(v: object) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float)):
        out = float(v)
    elif isinstance(v, str):
        try:
            out = float(v)
        except ValueError:
            return None
    else:
        return None
    if not math.isfinite(out):
        return None
    return out


def esc(s: object) -> str:
    if s is None:
        return ""
    x = str(s)
    repl = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
        "<": r"\textless{}",
        ">": r"\textgreater{}",
    }
    return "".join(repl.get(ch, ch) for ch in x)


def write_csv(path: Path, rows: List[dict], cols: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in cols})


def write_csv_gz(path: Path, rows: List[dict], cols: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in cols})


def parse_key_audit_jsons(text: str) -> List[Tuple[dict, int]]:
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
        esc_ch = False
        end = None
        for pos in range(start, n):
            ch = text[pos]
            if in_string:
                if esc_ch:
                    esc_ch = False
                elif ch == "\\":
                    esc_ch = True
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


def rank_obj(obj: dict) -> Tuple[float, float]:
    step = to_float(obj.get("step"))
    tval = to_float(obj.get("t"))
    s = step if step is not None else float("-inf")
    t = tval if tval is not None else float("-inf")
    return (s, t)


def parse_log_pica_config(path: str, cache: Dict[str, Optional[dict]]) -> Optional[dict]:
    if path in cache:
        return cache[path]
    p = Path(path)
    if not p.exists():
        cache[path] = None
        return None
    text = p.read_text(encoding="utf-8", errors="replace")
    payloads = parse_key_audit_jsons(text)
    if not payloads:
        cache[path] = None
        return None
    best_obj, _ = max(payloads, key=lambda x: (rank_obj(x[0]), x[1]))
    pat = best_obj.get("pica_config")
    if isinstance(pat, dict):
        cache[path] = pat
        return pat
    cache[path] = None
    return None


def enabled_cells(enabled: list) -> List[str]:
    out = []
    for i, row in enumerate(enabled):
        for j, v in enumerate(row):
            if bool(v):
                out.append(f"P{i+1}<-P{j+1}")
    return sorted(out, key=lambda s: (int(s.split("<-")[0][1:]), int(s.split("<-")[1][1:])))


def enabled_hash(enabled: list) -> str:
    bits = []
    for row in enabled:
        bits.append("".join("1" if bool(v) else "0" for v in row))
    return "|".join(bits)


def infer_wave2_log_identity(name: str) -> Tuple[str, Optional[int], Optional[int], str]:
    m = re.match(r"^(EXP-[^_]+)_s(\d+)_n(\d+)_(.+)\.log$", name)
    if m:
        return m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
    m = re.match(r"^(EXP-[^_]+)_s(\d+)_n(\d+)\.log$", name)
    if m:
        exp = m.group(1)
        cfg = "empty" if exp == "EXP-F1" else ""
        return exp, int(m.group(2)), int(m.group(3)), cfg
    return "", None, None, ""


def write_t2a_tex(path: Path, rows: List[dict]) -> None:
    lines: List[str] = []
    lines.append("% Auto-generated by paper/scripts/build_T2_tables.py")
    lines.append(r"\begin{table}[t]")
    lines.append(r"\scriptsize")
    lines.append(r"\centering")
    lines.append(r"\caption{Paper dataset overview by micro size (manifest-defined union).}")
    lines.append(r"\label{tab:T2A_dataset_overview}")
    lines.append(r"\begin{tabular}{lrrrrl l rrrr}")
    lines.append(r"\toprule")
    lines.append(r"$n$ & Runs & Configs & Seeds/config & Exp IDs & $\tau_{\mathrm{med}}$ & $\tau_{\min}$ & $\tau_{\max}$ & active$\tau$ rate & REV count & REV rate \\")
    lines.append(r"\midrule")
    for r in rows:
        lines.append(
            f"{esc(r['n'])} & {r['runs']} & {r['configs']} & {esc(r['seeds_per_(config,n)'])} & {esc(r['exp_ids_used'])} & "
            f"{r['tau_median']} & {r['tau_min']} & {r['tau_max']} & {r['active_tau_defined_rate']:.4f} & {r['REV_count']} & {r['REV_rate']:.4f} \\\\" 
        )
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_t2b_tex(path: Path, rows: List[dict]) -> None:
    lines: List[str] = []
    lines.append("% Auto-generated by paper/scripts/build_T2_tables.py")
    lines.append(r"\begin{table}[t]")
    lines.append(r"\scriptsize")
    lines.append(r"\centering")
    lines.append(r"\caption{Key conditions used in the main narrative under the manifest-defined dataset union.}")
    lines.append(r"\label{tab:T2B_key_conditions}")
    lines.append(r"\begin{tabular}{l r l l r r r}")
    lines.append(r"\toprule")
    lines.append(r"Condition & $|E|$ & lens & packaging & $\tau_{\mathrm{cap}}$ & $\tau_{\mathrm{med}}$ & active$\tau$ rate \\")
    lines.append(r"\midrule")
    for r in rows:
        lines.append(
            f"{esc(r['short_label'])} ({esc(r['config_name'])}) & {r['E_enabled_count']} & {esc(r['lens_selector'])} & "
            f"{esc(r['packaging_selector'])} & {esc(r['p3_p3_tau_cap'])} & {r['tau_median_all']} & {r['active_tau_defined_rate_all']:.4f} \\\\" 
        )
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_t2c_tex(path: Path, rows: List[dict]) -> None:
    lines: List[str] = []
    lines.append("% Auto-generated by paper/scripts/build_T2_tables.py")
    lines.append(r"\begin{table}[t]")
    lines.append(r"\scriptsize")
    lines.append(r"\centering")
    lines.append(r"\caption{Wave\_2 ($n=256$) experiment suites: expected jobs, extracted audits, and paper-use status.}")
    lines.append(r"\label{tab:T2C_n256_suites}")
    lines.append(r"\begin{tabular}{l r r r l c p{0.26\linewidth}}")
    lines.append(r"\toprule")
    lines.append(r"Exp ID & Configs & Jobs expected & Audits extracted & Seeds & Used in paper & Notes \\")
    lines.append(r"\midrule")
    for r in rows:
        lines.append(
            f"{esc(r['exp_id'])} & {r['configs']} & {r['jobs_expected']} & {r['audits_extracted']} & {esc(r['seeds'])} & "
            f"{esc(r['used_in_paper'])} & {esc(r['notes'])} \\\\" 
        )
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()

    out_tables = Path(args.out_tables)
    out_figdata = Path(args.out_figdata)
    out_tables.mkdir(parents=True, exist_ok=True)
    out_figdata.mkdir(parents=True, exist_ok=True)

    t2a_tex = out_tables / "T2A_dataset_overview.tex"
    t2b_tex = out_tables / "T2B_key_conditions.tex"
    t2c_tex = out_tables / "T2C_n256_suites.tex"
    t2a_csv = out_figdata / "T2A_dataset_overview.csv"
    t2a_csv_gz = out_figdata / "T2A_dataset_overview.csv.gz"
    t2b_csv = out_figdata / "T2B_key_conditions.csv"
    t2b_csv_gz = out_figdata / "T2B_key_conditions.csv.gz"
    t2c_csv = out_figdata / "T2C_n256_suites.csv"
    t2c_csv_gz = out_figdata / "T2C_n256_suites.csv.gz"
    qa_path = Path(args.qa_out)

    if not args.force:
        for p in [t2a_tex, t2b_tex, t2c_tex, t2a_csv, t2a_csv_gz, t2b_csv, t2b_csv_gz, t2c_csv, t2c_csv_gz, qa_path]:
            if p.exists():
                raise SystemExit(f"Output exists: {p} (use --force)")

    run = pd.read_csv(args.run_summary)
    run["n"] = pd.to_numeric(run["n"], errors="coerce")
    run["seed"] = pd.to_numeric(run["seed"], errors="coerce")
    run["tau"] = pd.to_numeric(run["tau"], errors="coerce")
    run["active_tau"] = pd.to_numeric(run["active_tau"], errors="coerce")
    run = run.dropna(subset=["n", "seed"]).copy()
    run["n"] = run["n"].astype(int)
    run["seed"] = run["seed"].astype(int)
    run["is_REV_bool"] = run["is_REV"].map(to_bool)

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    dataset_ids = sorted(manifest.get("datasets", {}).keys())

    # T2A overview rows
    t2a_rows: List[dict] = []
    for nval in sorted(run["n"].unique().tolist()):
        sub = run[run["n"] == nval].copy()
        seed_counts = sub.groupby(["config_name", "n"]) ["seed"].nunique().tolist()
        smin = int(min(seed_counts)) if seed_counts else 0
        smed = float(statistics.median(seed_counts)) if seed_counts else float("nan")
        smax = int(max(seed_counts)) if seed_counts else 0
        exp_ids_used = ",".join(sorted(sub["exp_id"].astype(str).unique().tolist()))
        t2a_rows.append(
            {
                "n": nval,
                "runs": int(len(sub)),
                "configs": int(sub["config_name"].nunique()),
                "exp_ids_used": exp_ids_used,
                "seeds_per_(config,n)": f"{smin}/{int(smed) if math.isfinite(smed) else ''}/{smax}",
                "tau_median": float(sub["tau"].median()) if len(sub) else float("nan"),
                "tau_min": float(sub["tau"].min()) if len(sub) else float("nan"),
                "tau_max": float(sub["tau"].max()) if len(sub) else float("nan"),
                "active_tau_defined_rate": float(sub["active_tau"].notna().mean()) if len(sub) else float("nan"),
                "REV_count": int(sub["is_REV_bool"].sum()),
                "REV_rate": float(sub["is_REV_bool"].mean()) if len(sub) else float("nan"),
            }
        )

    seed_counts_all = run.groupby(["config_name", "n"]) ["seed"].nunique().tolist()
    smin_all = int(min(seed_counts_all)) if seed_counts_all else 0
    smed_all = float(statistics.median(seed_counts_all)) if seed_counts_all else float("nan")
    smax_all = int(max(seed_counts_all)) if seed_counts_all else 0
    t2a_rows.append(
        {
            "n": "ALL",
            "runs": int(len(run)),
            "configs": int(run["config_name"].nunique()),
            "exp_ids_used": ",".join(sorted(run["exp_id"].astype(str).unique().tolist())),
            "seeds_per_(config,n)": f"{smin_all}/{int(smed_all) if math.isfinite(smed_all) else ''}/{smax_all}",
            "tau_median": float(run["tau"].median()) if len(run) else float("nan"),
            "tau_min": float(run["tau"].min()) if len(run) else float("nan"),
            "tau_max": float(run["tau"].max()) if len(run) else float("nan"),
            "active_tau_defined_rate": float(run["active_tau"].notna().mean()) if len(run) else float("nan"),
            "REV_count": int(run["is_REV_bool"].sum()),
            "REV_rate": float(run["is_REV_bool"].mean()) if len(run) else float("nan"),
        }
    )

    t2a_cols = [
        "n",
        "runs",
        "configs",
        "exp_ids_used",
        "seeds_per_(config,n)",
        "tau_median",
        "tau_min",
        "tau_max",
        "active_tau_defined_rate",
        "REV_count",
        "REV_rate",
    ]

    # pica_config extraction and consistency from log_file paths in run_summary
    pica_cache: Dict[str, Optional[dict]] = {}
    cfg_to_fps: Dict[str, Counter] = defaultdict(Counter)
    cfg_to_pica_by_fp: Dict[str, Dict[str, dict]] = defaultdict(dict)

    for cfg, sub in run.groupby("config_name"):
        paths = sorted(sub["log_file"].dropna().astype(str).unique().tolist())
        for path in paths:
            pat = parse_log_pica_config(path, pica_cache)
            if not isinstance(pat, dict):
                continue
            en = pat.get("enabled")
            if not (isinstance(en, list) and len(en) == 6 and all(isinstance(r, list) and len(r) == 6 for r in en)):
                continue
            fp = enabled_hash(en)
            cfg_to_fps[cfg][fp] += 1
            cfg_to_pica_by_fp[cfg][fp] = pat

    # T2B key-conditions rows
    t2b_rows: List[dict] = []
    key_missing = []
    key_consistency = {}
    key_summary = {}
    for cfg in KEY_CONFIGS:
        if cfg not in cfg_to_fps or not cfg_to_fps[cfg]:
            key_missing.append(cfg)
            key_consistency[cfg] = False
            continue
        key_consistency[cfg] = len(cfg_to_fps[cfg]) == 1
        fp, _ = cfg_to_fps[cfg].most_common(1)[0]
        pat = cfg_to_pica_by_fp[cfg][fp]
        en = pat["enabled"]
        en_cells = enabled_cells(en)
        sub = run[run["config_name"] == cfg]
        row = {
            "config_name": cfg,
            "short_label": SHORT_LABELS.get(cfg, cfg),
            "E_enabled_count": int(sum(1 for r in en for v in r if bool(v))),
            "enabled_cells": ";".join(en_cells),
            "lens_selector": pat.get("lens_selector", ""),
            "packaging_selector": pat.get("packaging_selector", ""),
            "p3_p3_tau_cap": pat.get("p3_p3_tau_cap", ""),
            "tau_median_all": float(sub["tau"].median()) if len(sub) else float("nan"),
            "active_tau_defined_rate_all": float(sub["active_tau"].notna().mean()) if len(sub) else float("nan"),
            "p2_p6_sbrc_strength": pat.get("p2_p6_sbrc_strength", ""),
            "p6_p6_dpi_cap_scale": pat.get("p6_p6_dpi_cap_scale", ""),
            "p6_p4_ep_boost": pat.get("p6_p4_ep_boost", ""),
            "p3_p6_mixer_strength": pat.get("p3_p6_mixer_strength", ""),
            "p3_p6_frob_scale": pat.get("p3_p6_frob_scale", ""),
            "rm_refresh_interval": pat.get("rm_refresh_interval", ""),
            "partition_interval": pat.get("partition_interval", ""),
            "packaging_interval": pat.get("packaging_interval", ""),
            "l1_audit_interval": pat.get("l1_audit_interval", ""),
            "p6_refresh_interval": pat.get("p6_refresh_interval", ""),
        }
        t2b_rows.append(row)
        key_summary[cfg] = {"enabled_count": row["E_enabled_count"], "enabled_hash": fp, "variants": int(len(cfg_to_fps[cfg]))}

    if key_missing:
        raise SystemExit(f"Missing required key configs from parsed pica_config: {key_missing}")

    t2b_cols = [
        "config_name",
        "short_label",
        "E_enabled_count",
        "enabled_cells",
        "lens_selector",
        "packaging_selector",
        "p3_p3_tau_cap",
        "tau_median_all",
        "active_tau_defined_rate_all",
        "p2_p6_sbrc_strength",
        "p6_p6_dpi_cap_scale",
        "p6_p4_ep_boost",
        "p3_p6_mixer_strength",
        "p3_p6_frob_scale",
        "rm_refresh_interval",
        "partition_interval",
        "packaging_interval",
        "l1_audit_interval",
        "p6_refresh_interval",
    ]

    # T2C n=256 wave_2 suites
    wave2_dir = Path(args.wave2_dir)
    wave2_logs = sorted(wave2_dir.glob("*.log"))
    jobs_by_exp = Counter()
    seeds_by_exp = defaultdict(set)
    cfgs_from_logs_by_exp = defaultdict(set)
    for p in wave2_logs:
        exp, seed, nval, cfg = infer_wave2_log_identity(p.name)
        if not exp:
            continue
        jobs_by_exp[exp] += 1
        if seed is not None:
            seeds_by_exp[exp].add(seed)
        if cfg:
            cfgs_from_logs_by_exp[exp].add(cfg)

    # config counts from wave2 manifest when available
    manifest_rows = json.loads(Path(args.wave2_manifest).read_text(encoding="utf-8"))
    cfgs_from_manifest_by_exp = defaultdict(set)
    for row in manifest_rows:
        if not isinstance(row, dict):
            continue
        exp = row.get("exp") or row.get("exp_id")
        cfg = row.get("config")
        if not isinstance(exp, str):
            continue
        if isinstance(cfg, str) and cfg:
            cfgs_from_manifest_by_exp[exp].add(cfg)
        elif exp == "EXP-F1":
            cfgs_from_manifest_by_exp[exp].add("empty")

    audits_by_exp = Counter()
    audits_cfgs_by_exp = defaultdict(set)
    with Path(args.wave2_audits).open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            exp = obj.get("exp_id")
            if isinstance(exp, str):
                audits_by_exp[exp] += 1
                cfg = obj.get("config_name")
                if isinstance(cfg, str) and cfg:
                    audits_cfgs_by_exp[exp].add(cfg)

    used_wave2_exp = set()
    for ds in manifest.get("datasets", {}).values():
        filt = ds.get("filters", {}) if isinstance(ds, dict) else {}
        if not isinstance(filt, dict):
            continue
        exp = filt.get("exp_id")
        nval = filt.get("n")
        n_in = filt.get("n_in")
        lfc = str(filt.get("log_file_contains", ""))
        if "/wave_2/" not in lfc:
            continue
        uses_n256 = (nval == 256) or (isinstance(n_in, list) and 256 in n_in)
        if uses_n256 and isinstance(exp, str):
            used_wave2_exp.add(exp)

    wave2_missing_count = sum(max(0, jobs_by_exp[e] - audits_by_exp.get(e, 0)) for e in jobs_by_exp)

    t2c_rows: List[dict] = []
    for exp in WAVE2_EXP_ORDER:
        cfgs = cfgs_from_manifest_by_exp.get(exp) or cfgs_from_logs_by_exp.get(exp, set())
        if not cfgs and audits_cfgs_by_exp.get(exp):
            cfgs = audits_cfgs_by_exp.get(exp, set())
        seeds = sorted(seeds_by_exp.get(exp, set()))
        seed_text = "" if not seeds else (f"{seeds[0]}-{seeds[-1]}" if len(seeds) > 1 else str(seeds[0]))
        jobs_expected = int(jobs_by_exp.get(exp, 0))
        extracted = int(audits_by_exp.get(exp, 0))
        notes = ""
        if exp == "EXP-112":
            notes = f"{wave2_missing_count} truncated logs overall; EXP-112 extracted={extracted}/{jobs_expected}"
        elif extracted < jobs_expected:
            notes = f"extracted={extracted}/{jobs_expected}"
        t2c_rows.append(
            {
                "exp_id": exp,
                "configs": int(len(cfgs)),
                "jobs_expected": jobs_expected,
                "audits_extracted": extracted,
                "seeds": seed_text,
                "used_in_paper": "yes" if exp in used_wave2_exp else "no",
                "notes": notes,
            }
        )

    t2c_cols = ["exp_id", "configs", "jobs_expected", "audits_extracted", "seeds", "used_in_paper", "notes"]

    # Write outputs
    write_csv(t2a_csv, t2a_rows, t2a_cols)
    write_csv_gz(t2a_csv_gz, t2a_rows, t2a_cols)
    write_csv(t2b_csv, t2b_rows, t2b_cols)
    write_csv_gz(t2b_csv_gz, t2b_rows, t2b_cols)
    write_csv(t2c_csv, t2c_rows, t2c_cols)
    write_csv_gz(t2c_csv_gz, t2c_rows, t2c_cols)
    write_t2a_tex(t2a_tex, t2a_rows)
    write_t2b_tex(t2b_tex, t2b_rows)
    write_t2c_tex(t2c_tex, t2c_rows)

    # QA JSON
    cfg_consistency = {cfg: (len(cfg_to_fps.get(cfg, {})) == 1 and len(cfg_to_fps.get(cfg, {})) > 0) for cfg in sorted(cfg_to_fps.keys())}
    qa = {
        "dataset_mode": "manifest_union",
        "manifest_path": args.manifest,
        "dataset_ids": dataset_ids,
        "runs_total": int(len(run)),
        "counts_by_n": {str(k): int(v) for k, v in run.groupby("n").size().to_dict().items()},
        "configs_by_n": {str(k): int(v) for k, v in run.groupby("n")["config_name"].nunique().to_dict().items()},
        "seeds_per_config_n_summary": {
            "min": int(run.groupby(["config_name", "n"])["seed"].nunique().min()),
            "median": float(statistics.median(run.groupby(["config_name", "n"])["seed"].nunique().tolist())),
            "max": int(run.groupby(["config_name", "n"])["seed"].nunique().max()),
        },
        "pica_config_consistency_all_configs": bool(all(cfg_consistency.values())) if cfg_consistency else False,
        "pica_config_consistency_key_configs": key_consistency,
        "key_config_enabled_summary": key_summary,
        "key_configs_required": KEY_CONFIGS,
        "key_configs_missing": key_missing,
        "wave2_suite_summary": {
            row["exp_id"]: {
                "jobs_expected": row["jobs_expected"],
                "audits_extracted": row["audits_extracted"],
                "used_in_paper": row["used_in_paper"],
            }
            for row in t2c_rows
        },
        "wave2_truncation_count": int(wave2_missing_count),
        "used_wave2_experiments_in_paper": sorted(used_wave2_exp),
    }
    qa_path.parent.mkdir(parents=True, exist_ok=True)
    qa_path.write_text(json.dumps(qa, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"wrote={t2a_tex}")
    print(f"wrote={t2b_tex}")
    print(f"wrote={t2c_tex}")
    print(f"wrote={t2a_csv_gz}")
    print(f"wrote={t2b_csv_gz}")
    print(f"wrote={t2c_csv_gz}")
    print(f"wrote={qa_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
