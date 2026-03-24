#!/usr/bin/env python3
"""Build internal claim-evidence map for n=256 integration planning (N4)."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List

import pandas as pd


REQUIRED_N3_IDS = [
    "Q1_competition_group_vs_full_action_lagr_diff_kl_k4",
    "Q2_gen3_A13_A14_A19_vs_full_action_tilde_diff_kl",
    "Q3_full_action_tilde_geo_r2_delta256m128",
    "Q4_REV_rate_n256_overall",
    "Q5_gen3_A13_A14_A19_vs_full_action_tilde_frob",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build claim map JSON + markdown summary.")
    p.add_argument("--main_tex", default="paper/main.tex")
    p.add_argument("--n3_csv", default="paper/figdata/N3_n256_key_questions.csv.gz")
    p.add_argument("--n3_memo", default="paper/figdata/N3_decision_memo.md")
    p.add_argument("--n3_qa", default="paper/figdata/N3_QA.json")
    p.add_argument("--manifest", default="paper/figdata/paper_dataset_manifest.json")
    p.add_argument("--wave2_missing", default="paper/figdata/wave2_missing_audit_logs.csv")
    p.add_argument("--build_report", default="paper/figdata/figdata_build_report.json")
    p.add_argument("--out_json", default="paper/figdata/claim_map.json")
    p.add_argument("--out_summary", default="paper/figdata/claim_map_summary.md")
    return p.parse_args()


def parse_results_claim_titles(tex_path: Path) -> Dict[str, str]:
    tex = tex_path.read_text(encoding="utf-8")
    m = re.search(r"\\section\{Results\}(.+?)\\section\{Discussion\}", tex, flags=re.S)
    if not m:
        return {}
    s = m.group(1)
    out = {}
    for full in re.findall(r"\\subsection\{(C\d+:.*?)\}", s):
        mm = re.match(r"(C\d+):\s*(.*)", full)
        if mm:
            out[mm.group(1)] = mm.group(2).strip()
    return out


def main() -> int:
    args = parse_args()
    out_json = Path(args.out_json)
    out_summary = Path(args.out_summary)
    out_json.parent.mkdir(parents=True, exist_ok=True)

    claim_titles = parse_results_claim_titles(Path(args.main_tex))
    n3 = pd.read_csv(args.n3_csv)
    n3_ids = set(n3["analysis_id"].astype(str))

    missing_req = [x for x in REQUIRED_N3_IDS if x not in n3_ids]
    if missing_req:
        raise SystemExit(f"Missing required N3 analysis IDs: {missing_req}")

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    n3_qa = json.loads(Path(args.n3_qa).read_text(encoding="utf-8"))
    build_report = json.loads(Path(args.build_report).read_text(encoding="utf-8"))

    ds_all = sorted(manifest["datasets"].keys())
    ds_wave3 = ["ds_exp112_wave3_n32_64_128_all"]
    ds_n256_controls = ["ds_expf1_wave2_n256_empty", "ds_exp107_wave2_n256_sweep"]
    ds_n256_sel = ["ds_exp112_wave2_n256_selective_unique"]

    wave2_missing_count = int(manifest.get("notes", {}).get("wave2_truncation_count", 0))

    decision = {
        "add_C7": False,
        "rationale": (
            "N3 decision memo is uniformly 'same' across Q1–Q5; n=256 currently confirms/qualifies "
            "existing claims but does not justify a distinct new claim block."
        ),
        "n256_caveat": (
            f"Wave_2 has {wave2_missing_count} truncated logs missing KEY_AUDIT_JSON; "
            "EXP-112 n=256 selective configs have partial seed coverage (min 5, median 8, max 9)."
        ),
    }

    claims: List[Dict[str, object]] = [
        {
            "claim_id": "C1",
            "title": claim_titles.get("C1", "Structure and arrow-of-time suppression"),
            "draft_claim_text": (
                "Full-Action/Full-All continue to show structure/time-asymmetry separation from controls; "
                "n=256 control-suite evidence is consistent with prior qualitative framing without strengthening."
            ),
            "scope_n": [32, 64, 128, 256],
            "coverage_notes": (
                "n=256 controls come from EXP-F1/EXP-107; EXP-112 n=256 excludes control configs by manifest policy."
            ),
            "strength_change_due_to_n256": "same",
            "primary_evidence_assets": ["F3", "T3", "N3"],
            "supporting_evidence_assets": ["T6", "F7", "F8"],
            "evidence_rows": [
                "Q3_full_action_tilde_geo_r2_delta256m128",
                "Q4_REV_rate_n256_overall",
            ],
            "asset_updates_required": [
                "F3 add n=256 control row/panel with explicit provenance annotation",
                "T3 add n=256 block with control-source note",
            ],
            "falsifiers": [
                "If updated n=256 F3 control panels invert baseline/full_action ordering with non-overlapping CIs.",
                "If n=256 controls exhibit high REV rates inconsistent with low-REV large-n behavior.",
            ],
        },
        {
            "claim_id": "C2",
            "title": claim_titles.get("C2", "Resolution-dependent Lagrange probe emergence"),
            "draft_claim_text": (
                "Resolution-linked probe behavior remains plausible at n=256 controls/generators, "
                "but current n=256 evidence is supportive/qualitative and not stronger than existing claims."
            ),
            "scope_n": [32, 64, 128, 256],
            "coverage_notes": (
                "n=256 selective suite includes generator configs with 9 seeds; competition configs include seed gaps."
            ),
            "strength_change_due_to_n256": "same",
            "primary_evidence_assets": ["F4", "T3", "N3"],
            "supporting_evidence_assets": ["T6"],
            "evidence_rows": [
                "Q2_gen3_A13_A14_A19_vs_full_action_tilde_diff_kl",
                "Q3_full_action_tilde_geo_r2_delta256m128",
            ],
            "asset_updates_required": [
                "F4 add n=256 control comparison panel",
                "T3 include n=256 medians for lagrange-related headline metrics",
            ],
            "falsifiers": [
                "If n=256 F4 updates remove ladder-dependent ordering across PLA2/geo/diff probes.",
                "If n=256 generator-vs-full deltas systematically reverse with CIs excluding zero.",
            ],
        },
        {
            "claim_id": "C3",
            "title": claim_titles.get("C3", "Regime separation robustness across scales"),
            "draft_claim_text": (
                "Robustness language extends to include n=256 as a selective-suite confirmation, "
                "with explicit caveats on incomplete EXP-112 selective seeds."
            ),
            "scope_n": [32, 64, 128, 256],
            "coverage_notes": (
                "n=256 includes 237 selected runs; not a full 69-config suite. "
                "Trend claims remain conditional on selective coverage."
            ),
            "strength_change_due_to_n256": "same",
            "primary_evidence_assets": ["F5", "T6", "N3"],
            "supporting_evidence_assets": ["F7", "F8", "T2"],
            "evidence_rows": [
                "Q3_full_action_tilde_geo_r2_delta256m128",
                "Q4_REV_rate_n256_overall",
            ],
            "asset_updates_required": [
                "F5 add optional n=256 selected-suite panel (or clearly scoped appendix diagnostic)",
                "T6 robustness checklist add n=256 selective coverage row",
            ],
            "falsifiers": [
                "If n=256 selected-suite scatter collapses to a single cluster after adding missing runs.",
                "If revised seed-complete n=256 reruns produce contradictory trend signs vs n=128.",
            ],
        },
        {
            "claim_id": "C4",
            "title": claim_titles.get("C4", "Ablation sensitivity and generator structure"),
            "draft_claim_text": (
                "Main LOO sensitivity claim remains anchored to n=32/64/128; n=256 adds targeted generator/row-removal "
                "consistency checks but is not a full LOO replacement."
            ),
            "scope_n": [32, 64, 128, 256],
            "coverage_notes": (
                "n=256 targeted checks use EXP-112 selective configs with partial seeds; no full n=256 LOO matrix."
            ),
            "strength_change_due_to_n256": "same",
            "primary_evidence_assets": ["F6", "T4", "N3"],
            "supporting_evidence_assets": ["T3", "T6"],
            "evidence_rows": [
                "Q2_gen3_A13_A14_A19_vs_full_action_tilde_diff_kl",
                "Q5_gen3_A13_A14_A19_vs_full_action_tilde_frob",
            ],
            "asset_updates_required": [
                "F6 optionally add n=256 targeted-check companion panel",
                "T4 note n=256 targeted subset used for generator consistency checks",
            ],
            "falsifiers": [
                "If n=256 targeted removals contradict n=32/64/128 sensitivity direction with stable CIs.",
                "If generator comparisons vanish after restoring truncated n=256 logs.",
            ],
        },
        {
            "claim_id": "C5",
            "title": claim_titles.get("C5", "Anchor-rung probe couplings"),
            "draft_claim_text": (
                "Current anchor-rung coupling claim remains based on n=32/64/128; "
                "n=256 extension is planned but not yet treated as stronger evidence."
            ),
            "scope_n": [32, 64, 128],
            "coverage_notes": (
                "No dedicated n=256 T5 rerun yet in paper assets; selective n=256 coverage supports planning only."
            ),
            "strength_change_due_to_n256": "not_applicable",
            "primary_evidence_assets": ["T5", "N3"],
            "supporting_evidence_assets": ["T6"],
            "evidence_rows": [
                "Q3_full_action_tilde_geo_r2_delta256m128",
            ],
            "asset_updates_required": [
                "T5 optional n=256 extension with explicit selective-scope caveat",
            ],
            "falsifiers": [
                "If n=256 anchor-rung correlations are weak/inconsistent after selective-scope controls.",
                "If multiple-testing-corrected n=256 effects contradict n=32/64/128 signs.",
            ],
        },
        {
            "claim_id": "C6",
            "title": claim_titles.get("C6", "Partition competition effect at k=4"),
            "draft_claim_text": (
                "n=256 retest for competition-family diffusion misfit is currently inconclusive "
                "(CI overlaps zero), so claim framing remains unchanged and non-strengthened."
            ),
            "scope_n": [32, 64, 128, 256],
            "coverage_notes": (
                "Competition configs at n=256 are selective and partially truncated (A16_only has 5 seeds)."
            ),
            "strength_change_due_to_n256": "same",
            "primary_evidence_assets": ["T5", "N3"],
            "supporting_evidence_assets": ["F4", "T6"],
            "evidence_rows": [
                "Q1_competition_group_vs_full_action_lagr_diff_kl_k4",
            ],
            "asset_updates_required": [
                "T5 add explicit n=256 competition retest row marked inconclusive/CI-overlap",
            ],
            "falsifiers": [
                "If completed n=256 competition coverage yields stable negative effect with CI excluding zero.",
                "If competition-group effect sign flips across reruns with adequate seed support.",
            ],
        },
    ]

    assets = {
        "F1": {
            "asset_id": "F1",
            "current_status": "exists_pre_n256",
            "needs_update_for_n256": False,
            "data_sources": [],
            "coverage_limitations": "Conceptual diagram; no data dependency.",
        },
        "F2": {
            "asset_id": "F2",
            "current_status": "exists_pre_n256",
            "needs_update_for_n256": False,
            "data_sources": ["ds_exp112_wave3_n32_64_128_all"],
            "coverage_limitations": "PICA taxonomy figure; n256 not required for base panel.",
        },
        "F3": {
            "asset_id": "F3",
            "current_status": "exists_pre_n256",
            "needs_update_for_n256": True,
            "data_sources": ds_wave3 + ds_n256_controls,
            "coverage_limitations": "n256 controls are split across EXP-F1/EXP-107 by design.",
        },
        "F4": {
            "asset_id": "F4",
            "current_status": "exists_pre_n256",
            "needs_update_for_n256": True,
            "data_sources": ds_wave3 + ["ds_exp107_wave2_n256_sweep"],
            "coverage_limitations": "n256 panel relies on EXP-107 controls; selective EXP-112 probes incomplete.",
        },
        "F5": {
            "asset_id": "F5",
            "current_status": "exists_pre_n256",
            "needs_update_for_n256": True,
            "data_sources": ds_all,
            "coverage_limitations": "n256 is a selected suite (237 runs), not full 69-config census.",
        },
        "F6": {
            "asset_id": "F6",
            "current_status": "exists_pre_n256",
            "needs_update_for_n256": True,
            "data_sources": ds_wave3 + ds_n256_sel,
            "coverage_limitations": "n256 supports targeted checks only; full LOO matrix remains n=32/64/128.",
        },
        "F7": {
            "asset_id": "F7",
            "current_status": "exists_pre_n256",
            "needs_update_for_n256": True,
            "data_sources": ds_all,
            "coverage_limitations": "n256 tau outcomes available; selective EXP-112 suite has seed gaps.",
        },
        "F8": {
            "asset_id": "F8",
            "current_status": "exists_pre_n256",
            "needs_update_for_n256": True,
            "data_sources": ds_all,
            "coverage_limitations": "n256 REV/missingness should be reported with selective-suite caveat.",
        },
        "T1": {
            "asset_id": "T1",
            "current_status": "exists_pre_n256",
            "needs_update_for_n256": False,
            "data_sources": [],
            "coverage_limitations": "PICA catalog is scale-independent.",
        },
        "T2": {
            "asset_id": "T2",
            "current_status": "exists_pre_n256",
            "needs_update_for_n256": True,
            "data_sources": ds_all,
            "coverage_limitations": "Must explicitly separate n256 control provenance and selective EXP-112 coverage.",
        },
        "T3": {
            "asset_id": "T3",
            "current_status": "exists_pre_n256",
            "needs_update_for_n256": True,
            "data_sources": ds_all,
            "coverage_limitations": "n256 rows should include incomplete-seed annotations for selective configs.",
        },
        "T4": {
            "asset_id": "T4",
            "current_status": "exists_pre_n256",
            "needs_update_for_n256": True,
            "data_sources": ds_all,
            "coverage_limitations": "Generator taxonomy should note n256 targeted subset usage.",
        },
        "T5": {
            "asset_id": "T5",
            "current_status": "exists_pre_n256",
            "needs_update_for_n256": True,
            "data_sources": ds_wave3 + ["ds_exp107_wave2_n256_sweep", "ds_exp112_wave2_n256_selective_unique"],
            "coverage_limitations": "n256 extension likely selective/inconclusive until seed-complete reruns.",
        },
        "T6": {
            "asset_id": "T6",
            "current_status": "exists_pre_n256",
            "needs_update_for_n256": True,
            "data_sources": ds_all,
            "coverage_limitations": "Must carry forward 26 truncated-log caveat and per-config seed deficits.",
        },
    }

    # Guards required by ticket
    all_claim_ids = [c["claim_id"] for c in claims]
    required_claims = [f"C{i}" for i in range(1, 7)]
    missing_claims = [c for c in required_claims if c not in all_claim_ids]
    if missing_claims:
        raise SystemExit(f"Missing required claims: {missing_claims}")

    evidence_union = set()
    for c in claims:
        ev = c.get("evidence_rows", [])
        if not isinstance(ev, list):
            raise SystemExit(f"{c['claim_id']} evidence_rows must be a list.")
        if len(c.get("falsifiers", [])) < 1:
            raise SystemExit(f"{c['claim_id']} must have at least one falsifier.")
        evidence_union.update(ev)
        if c["strength_change_due_to_n256"] == "stronger":
            if not c.get("asset_updates_required"):
                raise SystemExit(f"{c['claim_id']} marked stronger but missing asset_updates_required.")
            if not ev:
                raise SystemExit(f"{c['claim_id']} marked stronger but missing evidence_rows.")

    missing_required_evidence = [x for x in REQUIRED_N3_IDS if x not in evidence_union]
    if missing_required_evidence:
        raise SystemExit(f"Required N3 analysis IDs not referenced in claims: {missing_required_evidence}")

    claim_map = {
        "decision": decision,
        "claims": claims,
        "assets": assets,
        "inputs": {
            "main_tex": args.main_tex,
            "n3_csv": args.n3_csv,
            "n3_memo": args.n3_memo,
            "n3_qa": args.n3_qa,
            "manifest": args.manifest,
            "wave2_missing": args.wave2_missing,
            "figdata_build_report": args.build_report,
        },
        "context": {
            "wave2_truncation_count": wave2_missing_count,
            "n3_rows_total": int(len(n3)),
            "n3_rows_by_question": n3_qa.get("rows_by_question"),
            "figdata_counts_by_n": build_report.get("counts_by_n"),
            "figdata_counts_by_exp_id": build_report.get("counts_by_exp_id"),
            "results_claim_titles_detected": claim_titles,
            "required_n3_analysis_ids": REQUIRED_N3_IDS,
        },
    }

    out_json.write_text(json.dumps(claim_map, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines: List[str] = []
    lines.append("# Claim Map Summary (N4)")
    lines.append("")
    lines.append(f"- Decision add_C7: `{decision['add_C7']}`")
    lines.append(f"- Rationale: {decision['rationale']}")
    lines.append(f"- n256 caveat: {decision['n256_caveat']}")
    lines.append("")
    lines.append("## Claims (strength change)")
    for c in claims:
        lines.append(
            f"- {c['claim_id']}: `{c['strength_change_due_to_n256']}` | "
            f"scope_n={c['scope_n']} | primary={', '.join(c['primary_evidence_assets'])}"
        )
    lines.append("")
    lines.append("## Assets needing n256 update")
    for aid in sorted(assets.keys()):
        a = assets[aid]
        if a["needs_update_for_n256"]:
            lines.append(f"- {aid}: sources={a['data_sources']} | note={a['coverage_limitations']}")
    lines.append("")
    lines.append("## Mandatory N3 evidence IDs embedded")
    for rid in REQUIRED_N3_IDS:
        lines.append(f"- {rid}")
    lines.append("")
    lines.append("## Caveats")
    lines.append("- Wave_2 includes 26 truncated logs without KEY_AUDIT_JSON.")
    lines.append("- EXP-112 n=256 selective suite has partial seeds (min 5, median 8, max 9).")
    lines.append("- n=256 controls are split by provenance: empty from EXP-F1; baseline/full_action/full_all from EXP-107.")
    out_summary.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"wrote={out_json}")
    print(f"wrote={out_summary}")
    print(f"claims={len(claims)}")
    print(f"add_C7={decision['add_C7']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
