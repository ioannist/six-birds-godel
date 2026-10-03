#!/usr/bin/env python3
from __future__ import annotations

import csv
from pathlib import Path
import re
import sys
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
ALLOWED_DECISIONS = {"theorem_led_ready", "theorem_led_conditional_ready", "narrow_once_more", "hybrid_only"}
ALLOWED_STATUS = {"lead", "backup", "discard"}
ALLOWED_BRIDGE = {"thm_closure_saturation_operator_change", "thm_frozen_slice_representative_canonicality", "none"}

REQUIRED_FILES = [
    ROOT / "data" / "theorem_track" / "candidate_registry.yaml",
    ROOT / "data" / "theorem_track" / "lead_candidate.yaml",
    ROOT / "data" / "theorem_track" / "bridge_candidate.yaml",
    ROOT / "data" / "theorem_track" / "theorem_ladder.yaml",
    ROOT / "data" / "theorem_track" / "promotion_gate.yaml",
    ROOT / "data" / "theorem_track" / "arithmetic_candidate.yaml",
    ROOT / "data" / "theorem_track" / "lemma_dependency_graph.yaml",
    ROOT / "data" / "theorem_track" / "external_dependency_contract.yaml",
    ROOT / "data" / "theorem_track" / "primitive_role_contract.yaml",
    ROOT / "data" / "theorem_track" / "paper_mode_gate.yaml",
    ROOT / "data" / "theorem_track" / "frozen_paper_claim.yaml",
    ROOT / "data" / "theorem_track" / "theorem_package.yaml",
    ROOT / "data" / "theorem_track" / "assumption_box.yaml",
    ROOT / "data" / "theorem_track" / "internal_proof_inventory.yaml",
    ROOT / "data" / "theorem_track" / "external_discharge_inventory.yaml",
    ROOT / "data" / "theorem_track" / "out_of_scope.yaml",
    ROOT / "docs" / "manuscript" / "section_skeleton.yaml",
    ROOT / "docs" / "manuscript" / "theorem_placement_map.yaml",
    ROOT / "docs" / "manuscript" / "assumption_box_placement.yaml",
    ROOT / "docs" / "manuscript" / "citation_placement_map.yaml",
    ROOT / "docs" / "manuscript" / "figure_table_inventory.yaml",
    ROOT / "docs" / "manuscript" / "appendix_split.yaml",
    ROOT / "docs" / "manuscript" / "claim_source_map.yaml",
    ROOT / "results" / "ticket-t1" / "candidate_matrix.csv",
    ROOT / "results" / "ticket-t1" / "obstacle_register.yaml",
    ROOT / "results" / "ticket-t1" / "report.md",
    ROOT / "results" / "ticket-t1-1" / "ladder_matrix.csv",
    ROOT / "results" / "ticket-t1-1" / "report.md",
    ROOT / "results" / "ticket-t1-2" / "report.md",
    ROOT / "results" / "ticket-t1-2" / "bridge_status.yaml",
    ROOT / "results" / "ticket-t1-3" / "theorem_gap_matrix.csv",
    ROOT / "results" / "ticket-t1-3" / "report.md",
    ROOT / "results" / "ticket-t1-4" / "proof_status.yaml",
    ROOT / "results" / "ticket-t1-4" / "report.md",
    ROOT / "results" / "ticket-t1-5" / "contract_status.yaml",
    ROOT / "results" / "ticket-t1-5" / "report.md",
    ROOT / "results" / "ticket-t1-5a" / "role_alignment_matrix.csv",
    ROOT / "results" / "ticket-t1-5a" / "report.md",
    ROOT / "results" / "ticket-t1-6" / "vision_alignment_matrix.csv",
    ROOT / "results" / "ticket-t1-6" / "theorem_mode_decision.yaml",
    ROOT / "results" / "ticket-t1-6" / "report.md",
    ROOT / "results" / "ticket-t1-7" / "package_readiness.yaml",
    ROOT / "results" / "ticket-t1-7" / "report.md",
    ROOT / "results" / "ticket-w1" / "scaffold_status.yaml",
    ROOT / "src" / "lean" / "ClosureFrontier" / "TheoremTrack" / "Core.lean",
    ROOT / "src" / "lean" / "ClosureFrontier" / "TheoremTrack" / "Frontier.lean",
    ROOT / "src" / "lean" / "ClosureFrontier" / "TheoremTrack" / "ArithmeticCandidate.lean",
    ROOT / "src" / "lean" / "ClosureFrontier" / "TheoremTrack" / "ExternalBoundary.lean",
    ROOT / "src" / "lean" / "ClosureFrontier" / "TheoremTrack" / "Alignment.lean",
    ROOT / "src" / "lean" / "ClosureFrontier" / "TheoremTrack" / "PrimitiveRoles.lean",
    ROOT / "src" / "lean" / "ClosureFrontier" / "TheoremTrack" / "PaperMain.lean",
    ROOT / "src" / "lean" / "ClosureFrontier" / "TheoremTrack" / "Candidates.lean",
    ROOT / "data" / "theorem_track" / "strengthening_package.yaml",
    ROOT / "docs" / "findings" / "restricted_arithmetic_proof.yaml",
]

class ValidationError(Exception):
    pass


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValidationError(f"missing file: {path.relative_to(ROOT)}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValidationError(f"invalid yaml: {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValidationError(f"yaml must be mapping: {path.relative_to(ROOT)}")
    return data


def require_nonempty_csv(path: Path) -> None:
    with path.open("r", encoding="utf-8", newline="") as h:
        rows = list(csv.DictReader(h))
    if not rows:
        raise ValidationError(f"{path.relative_to(ROOT)} is empty")


def validate_strengthening(inventory: dict[str, Any], nodes: dict[str, Any]) -> None:
    """Check traceability and import boundaries; semantic proofs need Lean/review."""
    package = load_yaml(ROOT / "data/theorem_track/strengthening_package.yaml")
    proof = load_yaml(ROOT / package["arithmetic_results"]["concrete_instance"]["proof"])
    entries = {e["theorem_name"]: e for e in inventory["entries"]}
    if len(entries) != len(inventory["entries"]):
        raise ValidationError("proof inventory contains duplicate theorem names")

    def check_theorem(name: str, file: str | None = None) -> None:
        if name not in entries or entries[name].get("status") != "proved":
            raise ValidationError(f"strengthening theorem missing from proved inventory: {name}")
        if file is not None and entries[name]["file"] != file:
            raise ValidationError(f"strengthening theorem file mismatch: {name}")
        if name not in nodes:
            raise ValidationError(f"strengthening theorem missing from dependency graph: {name}")

    for result in package["native_results"]:
        check_theorem(result["theorem"], result["file"])
        for field in ("witness_theorem", "infinite_corollary", "counterexample_theorem"):
            if field in result:
                check_theorem(result[field], result["file"])
        for name in result.get("supporting_theorems", []):
            check_theorem(name, result["file"])
    arithmetic = package["arithmetic_results"]
    for name in arithmetic["concrete_instance"]["mechanized_bridges"]:
        check_theorem(name)
    check_theorem(arithmetic["general_restricted_class"]["theorem"],
                  arithmetic["general_restricted_class"]["file"])
    check_theorem(arithmetic["effectivity_boundary"]["quotient_bridge"])
    for step in proof["concrete_guarded_case"]["proof"]:
        names = step.get("lean", [])
        for name in [names] if isinstance(names, str) else names:
            check_theorem(name)
    for name in proof["general_first_consistency_case"]["lean"]:
        check_theorem(name)

    imports = {item["id"]: item for item in proof["imports"]}
    if len(imports) != len(proof["imports"]):
        raise ValidationError("arithmetic proof has duplicate import ids")
    for item in imports.values():
        if not all(item.get(field) for field in ("url", "location", "content_used", "lean_status")):
            raise ValidationError("arithmetic import lacks source or formalization scope")
    # Source theorem obligations must stay visible in the exported proof parameters.
    source_nodes = {
        "hWalsh": ("walsh_theorem_2_4_import_obligation", "walsh_dichotomy"),
        "hGodel": ("second_incompleteness_import_obligation", "second_incompleteness"),
    }
    for file in {e["file"] for e in entries.values() if e.get("proof_scope")}:
        source = (ROOT / file).read_text(encoding="utf-8")
        declarations = re.findall(r"^theorem\s+(\w+)(.*?)\s*:=", source, re.MULTILINE | re.DOTALL)
        for name, signature in declarations:
            check_theorem(name, file)
            for parameter, (node, import_id) in source_nodes.items():
                if re.search(rf"\b{parameter}\s*:", signature):
                    entry = entries[name]
                    if entry.get("depends_on_external_assumptions") is not True:
                        raise ValidationError(f"named arithmetic import hidden in inventory: {name}")
                    if not set(entry.get("arithmetic_application_imports", [])) <= imports.keys():
                        raise ValidationError(f"unknown arithmetic application import: {name}")
                    if import_id not in entry.get("arithmetic_application_imports", []):
                        raise ValidationError(f"arithmetic source mapping missing: {name}")
                    # The lift may inherit its source obligation through another theorem.
                    def reaches(start: str, target: str) -> bool:
                        return start == target or any(reaches(dep, target)
                            for dep in nodes[start].get("depends_on", []))
                    if not reaches(name, node):
                        raise ValidationError(f"named import missing from dependency graph: {name}")
    if (arithmetic["concrete_instance"]["full_EA_Lean_formalization"] is not False
            or arithmetic["general_restricted_class"]["source_proof_remechanized"] is not False
            or arithmetic["general_restricted_class"]["guard_is_in_this_global_class"] is not False
            or arithmetic["effectivity_boundary"]["quotient_computability_asserted"] is not False):
        raise ValidationError("strengthening package overstates its arithmetic/effectivity scope")


def main() -> int:
    try:
        for p in REQUIRED_FILES:
            if not p.exists():
                raise ValidationError(f"missing file: {p.relative_to(ROOT)}")

        role_contract = load_yaml(ROOT / "data" / "theorem_track" / "primitive_role_contract.yaml")
        if not isinstance(role_contract.get("entries"), list) or len(role_contract.get("entries")) != 6:
            raise ValidationError("primitive_role_contract must have exactly 6 entries")

        for yaml_path, required_list_field in [
            (ROOT / "data" / "theorem_track" / "assumption_box.yaml", "entries"),
            (ROOT / "data" / "theorem_track" / "internal_proof_inventory.yaml", "entries"),
            (ROOT / "data" / "theorem_track" / "external_discharge_inventory.yaml", "entries"),
            (ROOT / "data" / "theorem_track" / "out_of_scope.yaml", "entries"),
            (ROOT / "docs" / "manuscript" / "section_skeleton.yaml", "sections"),
            (ROOT / "docs" / "manuscript" / "theorem_placement_map.yaml", "placements"),
            (ROOT / "docs" / "manuscript" / "citation_placement_map.yaml", "entries"),
            (ROOT / "docs" / "manuscript" / "figure_table_inventory.yaml", "entries"),
            (ROOT / "docs" / "manuscript" / "appendix_split.yaml", "appendices"),
            (ROOT / "docs" / "manuscript" / "claim_source_map.yaml", "entries"),
        ]:
            doc = load_yaml(yaml_path)
            if not isinstance(doc.get(required_list_field), list) or not doc.get(required_list_field):
                raise ValidationError(f"{yaml_path.relative_to(ROOT)} missing non-empty {required_list_field}")

        gate = load_yaml(ROOT / "data" / "theorem_track" / "paper_mode_gate.yaml")
        if gate.get("decision_class") not in ALLOWED_DECISIONS:
            raise ValidationError("paper_mode_gate decision_class invalid")

        frozen_claim = load_yaml(ROOT / "data" / "theorem_track" / "frozen_paper_claim.yaml")
        if frozen_claim.get("statement_level") not in {"in_house", "conditional", "needs_narrowing"}:
            raise ValidationError("frozen_paper_claim statement_level invalid")
        if not frozen_claim.get("stable_main_theorem_name"):
            raise ValidationError("frozen_paper_claim missing stable_main_theorem_name")

        theorem_package = load_yaml(ROOT / "data" / "theorem_track" / "theorem_package.yaml")
        if not theorem_package.get("main_theorem_name"):
            raise ValidationError("theorem_package missing main_theorem_name")

        registry = load_yaml(ROOT / "data" / "theorem_track" / "candidate_registry.yaml")
        cand_entries = registry.get("entries")
        if not isinstance(cand_entries, list) or not cand_entries or len(cand_entries) > 4:
            raise ValidationError("candidate_registry entries invalid")
        ids: set[str] = set()
        lead_ids: list[str] = []
        for i, e in enumerate(cand_entries):
            if not isinstance(e, dict):
                raise ValidationError(f"entry[{i}] must be mapping")
            for field in ("id", "label", "theorem_tier", "hypothesis_bundle", "conclusion_shape", "support_modes", "known_counterexample_boundary", "viability_status"):
                if field not in e:
                    raise ValidationError(f"entry[{i}] missing field: {field}")
            cid = e["id"]
            if not isinstance(cid, str) or not cid or cid in ids:
                raise ValidationError(f"entry[{i}] invalid or duplicate id")
            ids.add(cid)
            if e["viability_status"] not in ALLOWED_STATUS:
                raise ValidationError(f"candidate {cid} invalid viability_status")
            if e["viability_status"] == "lead":
                lead_ids.append(cid)
        if len(lead_ids) > 1:
            raise ValidationError("candidate_registry has more than one lead candidate")

        lead_doc = load_yaml(ROOT / "data" / "theorem_track" / "lead_candidate.yaml")
        lead_id = lead_doc.get("lead_candidate_id")
        if not isinstance(lead_id, str) or not lead_id:
            raise ValidationError("lead_candidate_id missing or invalid")
        if lead_id != "none" and (lead_id not in ids or lead_ids != [lead_id]):
            raise ValidationError("lead candidate mismatch between registry and lead_candidate file")

        bridge_doc = load_yaml(ROOT / "data" / "theorem_track" / "bridge_candidate.yaml")
        if bridge_doc.get("selected_bridge_candidate_id") not in ALLOWED_BRIDGE:
            raise ValidationError("selected_bridge_candidate_id invalid")

        arithmetic_doc = load_yaml(ROOT / "data" / "theorem_track" / "arithmetic_candidate.yaml")
        proof = arithmetic_doc.get("proof_status")
        if not isinstance(proof, dict):
            raise ValidationError("arithmetic candidate proof_status must be mapping")
        if proof.get("formal_statement_in_lean") is not True or proof.get("conditional_lift_proved_in_lean") is not True:
            raise ValidationError("arithmetic candidate proof status incomplete")

        ext_contract = load_yaml(ROOT / "data" / "theorem_track" / "external_dependency_contract.yaml")
        if not isinstance(ext_contract.get("assumptions"), list) or not ext_contract.get("assumptions"):
            raise ValidationError("external dependency contract assumptions must be non-empty list")
        proof_driving_ids = {a.get("id") for a in ext_contract["assumptions"] if a.get("proof_driving")}
        if proof_driving_ids != {
            "ext_canonical_family_closed_in_domain", "ext_canonical_family_admissible",
            "ext_cone_canonicalization",
        }:
            raise ValidationError("external contract must record domain membership, canonical admissibility, and cone canonicalization")

        inventory = load_yaml(ROOT / "data" / "theorem_track" / "internal_proof_inventory.yaml")
        for entry in inventory["entries"]:
            path = ROOT / entry["file"]
            name = entry["theorem_name"]
            if not path.is_file() or not re.search(
                rf"^theorem\s+{re.escape(name)}\b", path.read_text(encoding="utf-8"), re.MULTILINE
            ):
                raise ValidationError(f"proof inventory theorem not declared in its listed file: {name}")

        ladder_doc = load_yaml(ROOT / "data" / "theorem_track" / "theorem_ladder.yaml")
        ordered = ladder_doc.get("ordered_entries")
        if not isinstance(ordered, list) or not ordered:
            raise ValidationError("theorem_ladder ordered_entries must be non-empty")
        tiers = [e.get("tier") for e in ordered if isinstance(e, dict)]
        for needed in ["base", "bridge", "arithmetic_candidate", "overreach_discarded"]:
            if needed not in tiers:
                raise ValidationError(f"theorem_ladder missing tier: {needed}")

        dep_graph = load_yaml(ROOT / "data" / "theorem_track" / "lemma_dependency_graph.yaml")
        nodes = dep_graph.get("nodes")
        if not isinstance(nodes, list) or not nodes:
            raise ValidationError("lemma_dependency_graph nodes must be non-empty list")
        for needed in ["restricted_in_house_alignment_lemma", "conditional_arithmetic_canonicality_lift"]:
            if not any(isinstance(n, dict) and n.get("id") == needed for n in nodes):
                raise ValidationError(f"dependency graph missing {needed}")
        by_id = {n["id"]: n for n in nodes}
        if len(by_id) != len(nodes):
            raise ValidationError("dependency graph contains duplicate node ids")
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node_id: str) -> None:
            if node_id not in by_id:
                raise ValidationError(f"dependency graph has unknown dependency: {node_id}")
            if node_id in visiting:
                raise ValidationError(f"dependency graph contains a cycle through: {node_id}")
            if node_id in visited:
                return
            visiting.add(node_id)
            for dependency in by_id[node_id].get("depends_on", []):
                visit(dependency)
            visiting.remove(node_id)
            visited.add(node_id)

        for node_id in by_id:
            visit(node_id)

        validate_strengthening(inventory, by_id)

        for status_file, required_fields in [
            (ROOT / "results" / "ticket-t1-2" / "bridge_status.yaml", ["statement_formalized", "core_saturation_proved", "bridge_result_proved", "depends_on_axioms_on_bridge_path", "boundary_consistent_with_current_evidence"]),
            (ROOT / "results" / "ticket-t1-4" / "proof_status.yaml", ["formalized_in_lean", "proved_in_lean", "depends_on_new_axioms", "depends_on_arithmetic_external_theorems"]),
            (ROOT / "results" / "ticket-t1-5" / "contract_status.yaml", ["contract_frozen", "conditional_lift_formalized", "conditional_lift_proved", "hidden_global_axioms_introduced"]),
            (ROOT / "results" / "ticket-t1-6" / "theorem_mode_decision.yaml", ["selected_decision_class", "supports_theorem_led_mode", "frozen_claim_level"]),
            (ROOT / "results" / "ticket-t1-7" / "package_readiness.yaml", ["frozen", "citation_linked", "lean_linked", "ready_for_paper_drafting", "stable_main_theorem_name", "hidden_assumptions_present"]),
            (ROOT / "results" / "ticket-w1" / "scaffold_status.yaml", ["carry_forward_t1_7_files_present", "manuscript_scaffold_created", "proof_empirical_role_confusion_corrected", "ready_for_non_prose_paper_execution"]),
        ]:
            doc = load_yaml(status_file)
            for field in required_fields:
                if field not in doc:
                    raise ValidationError(f"{status_file.relative_to(ROOT)} missing field: {field}")

        decision_doc = load_yaml(ROOT / "results" / "ticket-t1-6" / "theorem_mode_decision.yaml")
        if decision_doc.get("selected_decision_class") not in ALLOWED_DECISIONS:
            raise ValidationError("theorem_mode_decision selected_decision_class invalid")

        require_nonempty_csv(ROOT / "results" / "ticket-t1" / "candidate_matrix.csv")
        with (ROOT / "results" / "ticket-t1" / "candidate_matrix.csv").open("r", encoding="utf-8", newline="") as h:
            matrix_ids = {r.get("id", "") for r in csv.DictReader(h)}
        if not matrix_ids.issuperset(ids):
            raise ValidationError("candidate_matrix missing candidate ids from registry")
        for rel in [
            ROOT / "results" / "ticket-t1-1" / "ladder_matrix.csv",
            ROOT / "results" / "ticket-t1-3" / "theorem_gap_matrix.csv",
            ROOT / "results" / "ticket-t1-5a" / "role_alignment_matrix.csv",
            ROOT / "results" / "ticket-t1-6" / "vision_alignment_matrix.csv",
        ]:
            require_nonempty_csv(rel)

        obstacles = load_yaml(ROOT / "results" / "ticket-t1" / "obstacle_register.yaml")
        if not isinstance(obstacles.get("entries"), list) or not obstacles.get("entries"):
            raise ValidationError("obstacle_register entries must be non-empty list")

        for rp in [
            ROOT / "results" / "ticket-t1" / "report.md",
            ROOT / "results" / "ticket-t1-1" / "report.md",
            ROOT / "results" / "ticket-t1-2" / "report.md",
            ROOT / "results" / "ticket-t1-3" / "report.md",
            ROOT / "results" / "ticket-t1-4" / "report.md",
            ROOT / "results" / "ticket-t1-5" / "report.md",
            ROOT / "results" / "ticket-t1-5a" / "report.md",
            ROOT / "results" / "ticket-t1-6" / "report.md",
            ROOT / "results" / "ticket-t1-7" / "report.md",
        ]:
            if not rp.read_text(encoding="utf-8").strip():
                raise ValidationError(f"{rp.relative_to(ROOT)} must be non-empty")

    except ValidationError as exc:
        print(f"theorem track validation failed: {exc}")
        return 1

    print("theorem track validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
