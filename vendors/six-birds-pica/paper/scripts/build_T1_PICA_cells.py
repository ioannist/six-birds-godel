#!/usr/bin/env python3
"""Build T1 PICA cell catalog outputs (CSV/CSV.GZ + LaTeX longtable)."""

from __future__ import annotations

import csv
import gzip
from pathlib import Path


OUTPUT_CSV = Path("paper/figdata/T1_PICA_cells.csv")
OUTPUT_CSV_GZ = Path("paper/figdata/T1_PICA_cells.csv.gz")
OUTPUT_TEX = Path("paper/tables/T1_PICA_cells.tex")


def _row(cell_id: str, actor: str, informant: str, status_code: str, prereqs: str, semantics: str) -> dict:
    status_name = {
        "A": "Action",
        "I": "Implicit",
        "T": "Trivial",
        "U": "Undefined",
    }[status_code]
    return {
        "cell_id": cell_id,
        "actor": actor,
        "informant": informant,
        "pair": f"{actor}<-{informant}",
        "status_code": status_code,
        "status_name": status_name,
        "prereqs": prereqs,
        "semantics": semantics,
    }


def build_rows() -> list[dict]:
    rows = [
        # P1 row
        _row("A1", "P1", "P1", "A", "P1 rewrite history", "History cooldown (avoid rewriting recently perturbed rows)"),
        _row("A2", "P1", "P2", "A", "row sparsity / gated-edge counts", "Sparsity-guided row targeting"),
        _row("A3", "P1", "P3", "A", "route mismatch RM + active partition", "RM-directed rewrite toward macro consistency"),
        _row("A4", "P1", "P4", "A", "active partition (selected P4 lens)", "Sector-boundary targeting (near cluster boundaries)"),
        _row("A5", "P1", "P5", "A", "active packaging (selected P5)", "Packaging defect targeting (idempotence failure)"),
        _row("A6", "P1", "P6", "A", "audit metrics / budget ledger", "Budget-gated suppression of P1 when budget low"),
        # P2 row
        _row("A7", "P2", "P1", "A", "P1 rewrite history", "Protect rewrites (don't gate newly rewritten rows)"),
        _row("A8", "P2", "P2", "A", "P2 flip history / cooldown", "Flip cooldown (don't re-flip recent edges)"),
        _row("A9", "P2", "P3", "A", "route mismatch RM + active partition", "RM-guided gating (cross-cluster edges in high-RM clusters)"),
        _row("A10", "P2", "P4", "A", "active partition (selected P4 lens)", "Spectral-guided gating (inter-cluster gating bias)"),
        _row("A11", "P2", "P5", "A", "active packaging (selected P5)", "Package-boundary gating"),
        _row("A12", "P2", "P6", "A", "audit metrics / budget ledger", "SBRC (repairs free; violations penalized)"),
        # P3 row
        _row("I1", "P3", "P1", "I", "refresh cycle (implicit)", "implicit (RM refresh after P1)"),
        _row("I2", "P3", "P2", "I", "refresh cycle (implicit)", "implicit (RM refresh after P2)"),
        _row("A18", "P3", "P3", "A", "multi-scale RM convergence", "adaptive tau from multi-scale RM convergence"),
        _row("A19", "P3", "P4", "A", "active partition + per-sector RM", "per-sector mixing weights (high-RM sectors get more P1/P2)"),
        _row("A20", "P3", "P5", "A", "active packaging + per-package RM", "packaging-derived mixing bias"),
        _row("A13", "P3", "P6", "A", "audit metrics / budget ledger", "frob-modulated mixer (structure-driven explore/consolidate)"),
        # P4 row
        _row("I3", "P4", "P1", "I", "refresh cycle (implicit)", "implicit (partition refresh after P1)"),
        _row("I4", "P4", "P2", "I", "refresh cycle (implicit)", "implicit (partition refresh after P2)"),
        _row("A14", "P4", "P3", "A", "route mismatch RM", "RM-quantile partition"),
        _row("A15", "P4", "P4", "A", "active kernel spectrum", "spectral partition (canonical lens)"),
        _row("A16", "P4", "P5", "A", "active packaging (selected P5)", "package-derived partition"),
        _row("A17", "P4", "P6", "A", "audit metrics / EP flow", "EP-flow partition"),
        # P5 row
        _row("I5", "P5", "P1", "I", "refresh cycle (implicit)", "implicit (packaging refresh after P1)"),
        _row("I6", "P5", "P2", "I", "refresh cycle (implicit)", "implicit (packaging refresh after P2)"),
        _row("A21", "P5", "P3", "A", "route mismatch RM", "RM-similarity packaging"),
        _row("A22", "P5", "P4", "A", "active partition (selected P4 lens)", "sector-balanced packaging (split oversized clusters)"),
        _row("T2", "P5", "P5", "T", "tautology (trivial)", "packaging idempotence (trivial)"),
        _row("A23", "P5", "P6", "A", "audit metrics / EP profile", "EP-similarity packaging"),
        # P6 row
        _row("I7", "P6", "P1", "I", "refresh cycle (implicit)", "implicit (audit refresh after P1)"),
        _row("I8", "P6", "P2", "I", "refresh cycle (implicit)", "implicit (audit refresh after P2)"),
        _row("T3", "P6", "P3", "T", "tautology (trivial)", "trivial (RM is itself an audit metric; circular)"),
        _row("A24", "P6", "P4", "A", "active partition + per-sector EP", "sector-specific budget rate multiplier from per-sector EP"),
        _row("U1", "P6", "P5", "U", "undefined (circular)", "undefined (no clear non-circular action)"),
        _row("A25", "P6", "P6", "A", "audit metrics / retention ledger", "EP retention feedback cap (tighten when retention low)"),
    ]
    return rows


def validate_rows(rows: list[dict]) -> None:
    if len(rows) != 36:
        raise ValueError(f"Expected 36 rows, got {len(rows)}")

    seen_pairs = set()
    seen_ids = set()
    for r in rows:
        pair = (r["actor"], r["informant"])
        if pair in seen_pairs:
            raise ValueError(f"Duplicate actor/informant pair: {pair}")
        seen_pairs.add(pair)
        if r["cell_id"] in seen_ids:
            raise ValueError(f"Duplicate cell_id: {r['cell_id']}")
        seen_ids.add(r["cell_id"])

    counts = {"A": 0, "I": 0, "T": 0, "U": 0}
    for r in rows:
        counts[r["status_code"]] += 1
    expected = {"A": 25, "I": 8, "T": 2, "U": 1}
    if counts != expected:
        raise ValueError(f"Status counts mismatch: got {counts}, expected {expected}")

    undef = [r for r in rows if r["status_code"] == "U"]
    if len(undef) != 1:
        raise ValueError(f"Expected exactly one undefined row, got {len(undef)}")
    u = undef[0]
    if not (u["cell_id"] == "U1" and u["pair"] == "P6<-P5"):
        raise ValueError(f"Undefined row mismatch: {u}")


def write_csv(rows: list[dict]) -> None:
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "cell_id",
        "actor",
        "informant",
        "pair",
        "status_code",
        "status_name",
        "prereqs",
        "semantics",
    ]

    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    with gzip.open(OUTPUT_CSV_GZ, "wt", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def tex_escape(text: str) -> str:
    replacements = {
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
    out = []
    for ch in text:
        out.append(replacements.get(ch, ch))
    return "".join(out)


def write_tex(rows: list[dict]) -> None:
    OUTPUT_TEX.parent.mkdir(parents=True, exist_ok=True)

    colspec = "p{0.08\\linewidth} p{0.16\\linewidth} p{0.10\\linewidth} p{0.23\\linewidth} p{0.39\\linewidth}"
    lines = []
    lines.append("% Auto-generated by paper/scripts/build_T1_PICA_cells.py")
    lines.append("% Requires: \\usepackage{booktabs,longtable}")
    lines.append(f"\\begin{{longtable}}{{{colspec}}}")
    lines.append(
        "\\caption{PICA 6$\\times$6 cell catalog (A7.1): all actor$\\leftarrow$informant positions with class, prerequisites, and one-line semantics.}\\label{tab:T1_PICA_cells}\\\\"
    )
    lines.append("\\toprule")
    lines.append("Cell & Actor$\\leftarrow$Informant & Class & Prereqs & One-line semantics \\\\")
    lines.append("\\midrule")
    lines.append("\\endfirsthead")
    lines.append("\\toprule")
    lines.append("Cell & Actor$\\leftarrow$Informant & Class & Prereqs & One-line semantics \\\\")
    lines.append("\\midrule")
    lines.append("\\endhead")
    lines.append("\\bottomrule")
    lines.append("\\endfoot")
    lines.append("\\bottomrule")
    lines.append("\\endlastfoot")

    for r in rows:
        cell = tex_escape(r["cell_id"])
        pair = tex_escape(r["pair"])
        cls = tex_escape(r["status_name"])
        prereqs = tex_escape(r["prereqs"])
        sem = tex_escape(r["semantics"])
        lines.append(f"{cell} & {pair} & {cls} & {prereqs} & {sem} \\\\")

    lines.append("\\end{longtable}")

    OUTPUT_TEX.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    rows = build_rows()
    validate_rows(rows)
    write_csv(rows)
    write_tex(rows)
    print(f"wrote={OUTPUT_CSV}")
    print(f"wrote={OUTPUT_CSV_GZ}")
    print(f"wrote={OUTPUT_TEX}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
