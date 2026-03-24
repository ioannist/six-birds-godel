"""Closure Frontier Python API."""

from .finite_posets import FinitePoset, boolean_lattice, chain
from .frontier import CandidateScore, pareto_dominates, pareto_frontier
from .operators import FiniteMap
from .pica_adapter import (
    figdata_dir,
    inventory_key_surfaces,
    ledger_dir,
    list_figdata_files,
    list_ledger_files,
    load_primitives_yaml,
    probe_rust_workspace,
    primitives_yaml_path,
    repo_root,
    vendor_root,
)
from .scoring import (
    WeightedBenchmark,
    average_rank_lift_cost,
    coverage_score,
    max_rank_lift_cost,
    moved_points_cost,
    normalized_coverage_score,
    total_rank_lift_cost,
)

__all__ = [
    "CandidateScore",
    "FiniteMap",
    "FinitePoset",
    "WeightedBenchmark",
    "average_rank_lift_cost",
    "boolean_lattice",
    "chain",
    "coverage_score",
    "max_rank_lift_cost",
    "moved_points_cost",
    "normalized_coverage_score",
    "pareto_dominates",
    "pareto_frontier",
    "figdata_dir",
    "inventory_key_surfaces",
    "ledger_dir",
    "list_figdata_files",
    "list_ledger_files",
    "load_primitives_yaml",
    "probe_rust_workspace",
    "primitives_yaml_path",
    "repo_root",
    "smoke",
    "total_rank_lift_cost",
    "vendor_root",
]


def smoke() -> str:
    return "closure_frontier"
