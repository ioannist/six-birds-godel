#!/usr/bin/env python3
"""Build T4 ablation taxonomy + generators table assets."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import re
from glob import glob
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd


TOKEN = "KEY_AUDIT_JSON"
FAMILY_ORDER = [
    "Null",
    "Baseline skeleton",
    "Full",
    "Generators",
    "Leave-one-out",
    "Full amputations",
    "Actor-row subalgebras",
    "Informant-column subalgebras",
    "Singleton kernels",
    "Pair kernels",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build T4 taxonomy/generator tables.")
    parser.add_argument("--run_summary", default="paper/figdata/run_summary_table.csv.gz")
    parser.add_argument("--t1", default="paper/figdata/T1_PICA_cells.csv")
    parser.add_argument("--log_glob", default="lab/runs/campaign_v3/wave_3/wave_3/*.log")
    parser.add_argument("--out_tex", default="paper/tables/T4_taxonomy_generators.tex")
    parser.add_argument("--out_csv", default="paper/figdata/T4_taxonomy_generators.csv")
    parser.add_argument("--out_csv_gz", default="paper/figdata/T4_taxonomy_generators.csv.gz")
    parser.add_argument("--qa_out", default="paper/figdata/T4_QA.json")
    parser.add_argument("--exp", default="EXP-112")
    return parser.parse_args()


def to_int(value: object) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return None
    return None


def to_float(value: object) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        out = float(value)
    elif isinstance(value, str):
        try:
            out = float(value)
        except ValueError:
            return None
    else:
        return None
    if not math.isfinite(out):
        return None
    return out


def extract_key_audit_jsons(text: str) -> List[Tuple[dict, int]]:
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
        for p in range(start, n):
            ch = text[p]
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
                    end = p + 1
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


def parse_filename(path: str) -> Tuple[Optional[str], Optional[int], Optional[int], Optional[str]]:
    base = Path(path).name
    m = re.match(r"^(EXP-[^_]+)_s(\d+)_n(\d+)_(.+)\.log$", base)
    if not m:
        return None, None, None, None
    return m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)


def rank_obj(obj: dict) -> float:
    step = to_float(obj.get("step"))
    if step is not None:
        return step
    t_val = to_float(obj.get("t"))
    if t_val is not None:
        return t_val
    return float("-inf")


def canonical_json(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def escape_tex(text: object) -> str:
    if text is None:
        return ""
    s = str(text)
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
    return "".join(repl.get(ch, ch) for ch in s)


def cell_sort_key(cell_id: str) -> Tuple[int, int]:
    m = re.match(r"^([A-Z]+)(\d+)$", cell_id)
    if not m:
        return (99, 999)
    g = m.group(1)
    n = int(m.group(2))
    order = {"A": 0, "I": 1, "T": 2, "U": 3}.get(g, 9)
    return (order, n)


def pair_sort_key(pair: str) -> Tuple[int, int]:
    m = re.match(r"^P(\d+)<-P(\d+)$", pair)
    if not m:
        return (99, 99)
    return int(m.group(1)), int(m.group(2))


def parse_named_tokens(config_name: str) -> List[str]:
    toks = sorted(set(re.findall(r"A\d+", config_name)), key=cell_sort_key)
    return toks


def classify_family(config_name: str) -> Optional[str]:
    if config_name == "empty":
        return "Null"
    if config_name == "baseline":
        return "Baseline skeleton"
    if config_name in {"full_action", "full_all"}:
        return "Full"
    if config_name.startswith("gen"):
        return "Generators"
    if config_name.startswith("loo_"):
        return "Leave-one-out"
    if config_name.startswith("fa_no_"):
        return "Full amputations"
    if re.match(r"^P\d_row$", config_name) or re.match(r"^P\d(?:_P\d)+_rows$", config_name):
        return "Actor-row subalgebras"
    if re.match(r"^col_P\d+$", config_name):
        return "Informant-column subalgebras"
    if re.match(r"^A\d+_only$", config_name):
        return "Singleton kernels"
    if re.match(r"^A\d+_A\d+$", config_name) and not config_name.startswith("gen"):
        return "Pair kernels"
    return None


def write_csv(path: Path, rows: List[dict], columns: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=columns)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in columns})


def write_csv_gz(path: Path, rows: List[dict], columns: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=columns)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in columns})


def make_t4a_rows(
    family_counts: Dict[str, int],
    family_size_ranges: Dict[str, str],
    full_all_count: int,
    full_action_count: int,
    full_all_is_all_action: bool,
    full_action_removed_from_all: List[str],
    full_action_added_to_all: List[str],
) -> List[dict]:
    full_notes = []
    if full_all_is_all_action:
        full_notes.append(r"$S_{\mathrm{full\_all}}$ = all Action cells (verified)")
    else:
        full_notes.append(r"$S_{\mathrm{full\_all}}$ observed from logs")
    if not full_action_added_to_all:
        rem = ", ".join(full_action_removed_from_all) if full_action_removed_from_all else r"\varnothing"
        full_notes.append(r"$S_{\mathrm{full\_action}} = S_{\mathrm{full\_all}} \setminus \{" + rem + r"\}$")
    else:
        full_notes.append(r"$S_{\mathrm{full\_action}}$ differs from $S_{\mathrm{full\_all}}$ by + and $-$ cells")

    defs = {
        "Null": r"$S=\varnothing$",
        "Baseline skeleton": r"$S=S_0=\{P2\leftarrow P4,\;P4\leftarrow P4\}$",
        "Full": " ; ".join(full_notes),
        "Generators": r"$S=\mathrm{cl}(S_0\cup G)$ where $G$ from gen-name tokens",
        "Leave-one-out": r"$S=S_{\mathrm{full\_action}}\setminus\{c\}$",
        "Full amputations": r"$S=S_{\mathrm{full\_action}}\setminus D$",
        "Actor-row subalgebras": r"$S=\mathrm{cl}(S_0\cup\{c:\mathrm{actor}(c)\in R\})$",
        "Informant-column subalgebras": r"$S=\mathrm{cl}(S_0\cup\{c:\mathrm{informant}(c)=Pj\})$",
        "Singleton kernels": r"$S=\mathrm{cl}(S_0\cup\{A_i\})$",
        "Pair kernels": r"$S=\mathrm{cl}(S_0\cup\{A_i,A_j\})$",
    }
    patterns = {
        "Null": "`empty`",
        "Baseline skeleton": "`baseline`",
        "Full": "`full_action`, `full_all`",
        "Generators": "`gen*`",
        "Leave-one-out": "`loo_*`",
        "Full amputations": "`fa_no_*`",
        "Actor-row subalgebras": "`P*_row`, `P*_P*_rows`",
        "Informant-column subalgebras": "`col_P*`",
        "Singleton kernels": "`A*_only`",
        "Pair kernels": "`A*_A*` (non-gen)",
    }
    notes = {
        "Null": "No PICA cells enabled.",
        "Baseline skeleton": "Minimal structural scaffold (A10+A15).",
        "Full": f"Observed |S_full_action|={full_action_count}, |S_full_all|={full_all_count}.",
        "Generators": "Reusable low-cardinality generating subalgebras.",
        "Leave-one-out": "Single-cell removal tests around full_action.",
        "Full amputations": "Targeted amputations of full_action components.",
        "Actor-row subalgebras": "Actor-focused slices of PICA.",
        "Informant-column subalgebras": "Informant-focused slices of PICA.",
        "Singleton kernels": "One named action cell plus closure.",
        "Pair kernels": "Two named action cells plus closure.",
    }
    rows = []
    for fam in FAMILY_ORDER:
        rows.append(
            {
                "family": fam,
                "config_labels": patterns[fam],
                "algebraic_definition": defs[fam],
                "n_configs": family_counts.get(fam, 0),
                "enabled_count_range": family_size_ranges.get(fam, "NA"),
                "notes": notes[fam],
            }
        )
    return rows


def write_tex(
    path: Path,
    t4a_rows: List[dict],
    gen_rows: List[dict],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    lines.append("% Auto-generated by paper/scripts/build_T4_taxonomy_generators.py")
    lines.append(r"\begin{table*}[t]")
    lines.append(r"\scriptsize")
    lines.append(r"\centering")
    lines.append(r"\caption{T4A: EXP-112 ablation taxonomy as algebraic cell-set constraints.}")
    lines.append(r"\label{tab:T4A_taxonomy}")
    lines.append(r"\begin{tabular}{l l p{0.34\linewidth} r c p{0.20\linewidth}}")
    lines.append(r"\toprule")
    lines.append(r"Family & Config labels & Algebraic definition & \#configs & $|S|$ range & Notes \\")
    lines.append(r"\midrule")
    for r in t4a_rows:
        lines.append(
            f"{escape_tex(r['family'])} & {escape_tex(r['config_labels'])} & {r['algebraic_definition']} & "
            f"{r['n_configs']} & {escape_tex(r['enabled_count_range'])} & {escape_tex(r['notes'])} \\\\"
        )
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table*}")
    lines.append("")
    lines.append(r"\begin{table*}[t]")
    lines.append(r"\scriptsize")
    lines.append(r"\centering")
    lines.append(r"\caption{T4B: Generator subalgebras present in EXP-112 (config-level).}")
    lines.append(r"\label{tab:T4B_generators}")
    lines.append(r"\begin{tabular}{l r l l l}")
    lines.append(r"\toprule")
    lines.append(r"Generator config & $|S|$ & Named tokens & Extra closure cells & Enabled cells \\")
    lines.append(r"\midrule")
    for r in gen_rows:
        lines.append(
            f"{escape_tex(r['config_name'])} & {r['E_enabled_count']} & {escape_tex(r['named_tokens'])} & "
            f"{escape_tex(r['closure_extra_cells'])} & {escape_tex(r['enabled_cells_summary'])} \\\\"
        )
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table*}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()

    # Config universe from run summary.
    run_df = pd.read_csv(args.run_summary)
    run_df = run_df[run_df["exp_id"] == args.exp].copy()
    if run_df.empty:
        raise SystemExit(f"No rows for exp_id={args.exp} in run summary")
    configs = sorted(run_df["config_name"].dropna().unique().tolist())
    if len(configs) != 69:
        raise SystemExit(f"Expected 69 configs in run summary for {args.exp}, got {len(configs)}")

    # T1 mapping.
    t1 = pd.read_csv(args.t1)
    if len(t1) != 36:
        raise SystemExit(f"Expected 36 rows in T1 CSV, got {len(t1)}")
    pair_to_cell: Dict[str, str] = {}
    action_cells: List[str] = []
    for r in t1.itertuples(index=False):
        pair = str(r.pair)
        cell = str(r.cell_id)
        pair_to_cell[pair] = cell
        if str(r.status_code) == "A":
            action_cells.append(cell)
    action_cells = sorted(action_cells, key=cell_sort_key)
    action_cell_set = set(action_cells)

    # Parse logs and pick final record per run.
    selected: Dict[Tuple[str, str, int, int], dict] = {}
    log_paths = sorted(glob(args.log_glob))
    if not log_paths:
        raise SystemExit(f"No logs matched: {args.log_glob}")

    for path in log_paths:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        payloads = extract_key_audit_jsons(text)
        if not payloads:
            continue
        best_obj, _ = max(payloads, key=lambda p: (rank_obj(p[0]), p[1]))

        exp_f, seed_f, n_f, cfg_f = parse_filename(path)
        exp_obj = best_obj.get("exp_id") if isinstance(best_obj.get("exp_id"), str) else exp_f
        if exp_obj != args.exp:
            continue
        cfg_obj = best_obj.get("config_name") if isinstance(best_obj.get("config_name"), str) else cfg_f
        seed_obj = to_int(best_obj.get("seed"))
        n_obj = to_int(best_obj.get("n"))
        if seed_obj is None:
            seed_obj = seed_f
        if n_obj is None:
            n_obj = n_f
        if not isinstance(cfg_obj, str) or seed_obj is None or n_obj is None:
            continue
        run_id = (exp_obj, cfg_obj, int(n_obj), int(seed_obj))
        rank = (rank_obj(best_obj), Path(path).name)
        prev = selected.get(run_id)
        if prev is None or rank > prev["rank"]:
            selected[run_id] = {"obj": best_obj, "rank": rank, "log_file": Path(path).name}

    if len(selected) != 2070:
        raise SystemExit(f"Expected 2070 run records from logs for {args.exp}, got {len(selected)}")

    # Consistency: config -> pica_config identical across all runs.
    cfg_to_pat: Dict[str, dict] = {}
    cfg_to_pat_json: Dict[str, str] = {}
    mismatches: Dict[str, List[str]] = {}
    for run_id, item in sorted(selected.items()):
        cfg = run_id[1]
        obj = item["obj"]
        pica_cfg = obj.get("pica_config")
        if not isinstance(pica_cfg, dict):
            raise SystemExit(f"Missing pica_config for run_id={run_id}")
        encoded = canonical_json(pica_cfg)
        if cfg not in cfg_to_pat_json:
            cfg_to_pat_json[cfg] = encoded
            cfg_to_pat[cfg] = pica_cfg
        elif cfg_to_pat_json[cfg] != encoded:
            mismatches.setdefault(cfg, []).append(item["log_file"])
    if mismatches:
        raise SystemExit(f"pica_config mismatch across runs for configs: {sorted(mismatches.keys())}")

    # Check config universe matches.
    pica_configs = sorted(cfg_to_pat.keys())
    if configs != pica_configs:
        missing_in_logs = sorted(set(configs) - set(pica_configs))
        extra_in_logs = sorted(set(pica_configs) - set(configs))
        raise SystemExit(
            f"Config mismatch run_summary vs logs; missing_in_logs={missing_in_logs}, extra_in_logs={extra_in_logs}"
        )

    # Compute enabled sets per config.
    cfg_enabled_pairs: Dict[str, List[str]] = {}
    cfg_enabled_cells: Dict[str, List[str]] = {}
    for cfg in configs:
        pat = cfg_to_pat[cfg]
        enabled = pat.get("enabled")
        if not (
            isinstance(enabled, list)
            and len(enabled) == 6
            and all(isinstance(row, list) and len(row) == 6 for row in enabled)
        ):
            raise SystemExit(f"Invalid enabled matrix for config {cfg}")
        pairs = []
        cells = []
        for i, row in enumerate(enabled):
            for j, v in enumerate(row):
                if bool(v):
                    pair = f"P{i+1}<-P{j+1}"
                    pairs.append(pair)
                    if pair not in pair_to_cell:
                        raise SystemExit(f"Pair {pair} missing from T1 mapping")
                    cells.append(pair_to_cell[pair])
        cfg_enabled_pairs[cfg] = sorted(pairs, key=pair_sort_key)
        cfg_enabled_cells[cfg] = sorted(cells, key=cell_sort_key)

    # Baseline and full references.
    s0_pairs = {"P2<-P4", "P4<-P4"}
    s0_cells = {pair_to_cell[p] for p in sorted(s0_pairs, key=pair_sort_key)}
    full_action_set = set(cfg_enabled_cells["full_action"])
    full_all_set = set(cfg_enabled_cells["full_all"])
    full_all_minus_full_action = sorted(full_all_set - full_action_set, key=cell_sort_key)
    full_action_minus_full_all = sorted(full_action_set - full_all_set, key=cell_sort_key)
    full_all_is_all_action = full_all_set == action_cell_set

    # Per-config rows.
    rows: List[dict] = []
    family_counts: Dict[str, int] = {f: 0 for f in FAMILY_ORDER}
    unassigned: List[str] = []
    duplicate_assignments: List[str] = []
    loo_checks: Dict[str, dict] = {}
    gen_configs: List[str] = []

    for cfg in configs:
        family = classify_family(cfg)
        if family is None:
            unassigned.append(cfg)
            continue
        if family not in FAMILY_ORDER:
            duplicate_assignments.append(cfg)
            continue
        family_counts[family] += 1
        if family == "Generators":
            gen_configs.append(cfg)

        enabled_pairs = cfg_enabled_pairs[cfg]
        enabled_cells = cfg_enabled_cells[cfg]
        enabled_set = set(enabled_cells)
        named_tokens = parse_named_tokens(cfg)
        named_set = set(named_tokens)
        closure_extra = sorted(enabled_set - s0_cells - named_set, key=cell_sort_key)

        if family in {"Leave-one-out", "Full amputations"}:
            removed = sorted(full_action_set - enabled_set, key=cell_sort_key)
            added = sorted(enabled_set - full_action_set, key=cell_sort_key)
        else:
            removed = []
            added = []

        if family == "Leave-one-out":
            ok = len(removed) == 1 and len(added) == 0
            loo_checks[cfg] = {"removed": removed, "added": added, "ok": ok}
            if not ok:
                raise SystemExit(
                    f"LOO invariant failed for {cfg}: removed={removed}, added={added} (need exactly one removed, none added)"
                )

        notes = {
            "Null": "No cells enabled.",
            "Baseline skeleton": "Contains only S0 scaffold.",
            "Full": "Reference full configurations.",
            "Generators": "Named generator-based subalgebra.",
            "Leave-one-out": "Single-cell removal from full_action.",
            "Full amputations": "Targeted amputation from full_action.",
            "Actor-row subalgebras": "Actor row-set constrained config.",
            "Informant-column subalgebras": "Informant column constrained config.",
            "Singleton kernels": "Single named action with closure.",
            "Pair kernels": "Two named actions with closure.",
        }[family]

        rows.append(
            {
                "config_name": cfg,
                "family": family,
                "E_enabled_count": len(enabled_cells),
                "enabled_cells_P": "; ".join(enabled_pairs),
                "enabled_cells_A": "; ".join(enabled_cells),
                "base_included": all(p in set(enabled_pairs) for p in s0_pairs),
                "delta_vs_full_action_removed": "; ".join(removed),
                "delta_vs_full_action_added": "; ".join(added),
                "named_tokens": "; ".join(named_tokens),
                "closure_extra_cells": "; ".join(closure_extra),
                "notes": notes,
            }
        )

    if unassigned:
        raise SystemExit(f"Unassigned configs detected: {unassigned}")
    if duplicate_assignments:
        raise SystemExit(f"Duplicate assignment errors: {duplicate_assignments}")
    if len(rows) != 69:
        raise SystemExit(f"Expected 69 rows, got {len(rows)}")

    # Family size ranges.
    family_size_ranges: Dict[str, str] = {}
    by_family: Dict[str, List[int]] = {}
    for r in rows:
        by_family.setdefault(r["family"], []).append(int(r["E_enabled_count"]))
    for fam in FAMILY_ORDER:
        vals = by_family.get(fam, [])
        if not vals:
            family_size_ranges[fam] = "NA"
        else:
            family_size_ranges[fam] = f"{min(vals)}-{max(vals)}"

    # Build T4A and T4B data.
    t4a_rows = make_t4a_rows(
        family_counts=family_counts,
        family_size_ranges=family_size_ranges,
        full_all_count=len(full_all_set),
        full_action_count=len(full_action_set),
        full_all_is_all_action=full_all_is_all_action,
        full_action_removed_from_all=sorted(full_all_set - full_action_set, key=cell_sort_key),
        full_action_added_to_all=sorted(full_action_set - full_all_set, key=cell_sort_key),
    )
    gen_configs = sorted(gen_configs)
    gen_rows = []
    for cfg in gen_configs:
        row = next(r for r in rows if r["config_name"] == cfg)
        enabled_summary = "see CSV"
        gen_rows.append(
            {
                "config_name": cfg,
                "E_enabled_count": row["E_enabled_count"],
                "named_tokens": row["named_tokens"] if row["named_tokens"] else "none",
                "closure_extra_cells": row["closure_extra_cells"] if row["closure_extra_cells"] else "none",
                "enabled_cells_summary": enabled_summary,
            }
        )

    # Sort config-level CSV by family then name.
    fam_rank = {f: i for i, f in enumerate(FAMILY_ORDER)}
    rows = sorted(rows, key=lambda r: (fam_rank[r["family"]], r["config_name"]))

    columns = [
        "config_name",
        "family",
        "E_enabled_count",
        "enabled_cells_P",
        "enabled_cells_A",
        "base_included",
        "delta_vs_full_action_removed",
        "delta_vs_full_action_added",
        "named_tokens",
        "closure_extra_cells",
        "notes",
    ]
    out_csv = Path(args.out_csv)
    out_csv_gz = Path(args.out_csv_gz)
    out_tex = Path(args.out_tex)
    qa_out = Path(args.qa_out)

    write_csv(out_csv, rows, columns)
    write_csv_gz(out_csv_gz, rows, columns)
    write_tex(out_tex, t4a_rows, gen_rows)

    qa = {
        "exp_id": args.exp,
        "config_count": len(rows),
        "family_counts": family_counts,
        "unassigned": unassigned,
        "duplicate_assignments": duplicate_assignments,
        "full_action_enabled_count": len(full_action_set),
        "full_all_enabled_count": len(full_all_set),
        "full_all_minus_full_action": full_all_minus_full_action,
        "full_action_minus_full_all": full_action_minus_full_all,
        "full_all_is_all_action_cells": full_all_is_all_action,
        "loo_checks": loo_checks,
        "gen_configs": gen_configs,
    }
    qa_out.parent.mkdir(parents=True, exist_ok=True)
    qa_out.write_text(json.dumps(qa, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"wrote={out_tex}")
    print(f"wrote={out_csv}")
    print(f"wrote={out_csv_gz}")
    print(f"wrote={qa_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

