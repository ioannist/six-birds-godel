# Six Birds: Gödel

This repository contains the **incompleteness/foundations theorem-track repository** for the paper:

> **Six Birds for Incompleteness: Fixed Packages, Package Change, and Conditional Arithmetic Lift**
>
> Archived at: https://zenodo.org/records/19201835
>
> DOI: https://doi.org/10.5281/zenodo.19201835

This paper is the incompleteness-focused instantiation of the emergence calculus introduced in *Six Birds: Foundations of Emergence Calculus*. It develops a theorem-led package language for theory growth: fixed packages, package change, frozen-slice comparison, and a conditional arithmetic lift under an explicit external dependency contract.

## What this repository provides

The incompleteness instantiation implements:

- **Lean theorem track**: in-house theorem surfaces for fixed-package saturation, package-change necessity, frozen-slice comparison, efficiency transfer, and restricted alignment under `src/lean/`
- **Python comparison layer**: finite-poset, operator, frontier, and scoring utilities under `src/python/closure_frontier/`
- **Theorem-package registries**: machine-readable assumption boxes, candidate registries, dependency graphs, primitive-role contracts, and theorem ladders under `data/theorem_track/`
- **Vendor-backed support bridge**: normalized PICA records, atlas/mapping layers, and supporting claim backings under `data/pica_*` and `vendors/six-birds-pica/`
- **Manuscript build artifacts**: canonical PDF and flattened TeX output under `paper/build/`
- **Snapshot-visible audit trail**: ticket outputs and revision ledgers under `results/`, including manuscript assembly, theorem-surfacing audits, and appendix/body boundary checks

## Scope and limitations

The paper is explicit about what it does and does not establish:

- The internal theorem ladder is in-house and Lean-backed, but the arithmetic lift is conditional on an explicit external dependency contract
- The manuscript does not prove an unconditional global canonicality theorem
- Vendor-backed PICA evidence supports primitive-role and scope discipline, but does not discharge theorem obligations
- The broader Six-Birds and PICA interaction spaces are not reduced here to one universal theorem summary; the paper works on a deliberately frozen slice

## Install

```bash
pip install -e .[dev]
lake build
```

## Test

```bash
make check
```

## Build paper

```bash
make paper-build
```

Canonical outputs:

- `paper/build/main.pdf`
- `paper/build/main_flattened.tex`
