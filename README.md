# Six Birds: Gödel

This repository contains the **incompleteness/foundations theorem-track repository** for the paper:

> **Six Birds for Incompleteness: Fixed Packages, Package Change, and Conditional Arithmetic Lift**
>
> v2 (October 3, 2026): https://doi.org/10.5281/zenodo.23119453
>
> v1 (March 24, 2026): https://doi.org/10.5281/zenodo.19201835 (archived at https://zenodo.org/records/19201835)

This paper is the incompleteness-focused instantiation of the emergence calculus introduced in *Six Birds: Foundations of Emergence Calculus*. It develops a package language for theory growth: fixed packages saturate, package changes are witnessed by explicit differing points, state changes are bounded by package switches, efficiency on a frozen ledger transfers along cone agreement, and a conditional canonical-representative theorem holds under an explicit three-clause contract. A concrete guarded-consistency case in elementary arithmetic and a restricted class via Walsh's dichotomy use cited arithmetic theorems as explicit hypotheses. The current manuscript is v2 (October 3, 2026).

## What this repository provides

The incompleteness instantiation implements:

- **Lean theorem track**: fixed-package saturation, witnessed package change, the package-switch budget and its sharpness, frozen-ledger efficiency transfer, restricted alignment, the invariant-ledger selection boundary, the conditional main theorem, and the arithmetic bridges under `src/lean/`
- **Python comparison layer**: finite-poset, operator, frontier, and scoring utilities under `src/python/closure_frontier/`
- **Theorem-package registries**: machine-readable assumption boxes, candidate registries, dependency graphs, primitive-role contracts, and theorem ladders under `data/theorem_track/`
- **Vendor-backed support bridge**: normalized PICA records, atlas/mapping layers, and supporting claim backings under `data/pica_*` and `vendors/six-birds-pica/`
- **Manuscript build artifacts**: canonical PDF and flattened TeX output under `paper/build/`
- **Snapshot-visible audit trail**: ticket outputs and revision ledgers under `results/`, including manuscript assembly, theorem-surfacing audits, and appendix/body boundary checks

## Scope and limitations

The paper is explicit about what it does and does not establish:

- The internal theorem ladder is in-house and Lean-backed, but the arithmetic lift is conditional on an explicit external dependency contract
- The manuscript does not prove an unconditional global canonicality theorem
- The arithmetic results rely on second incompleteness and Walsh's dichotomy as cited theorems, entered as explicit Lean hypotheses; EA's proof calculus is not implemented in Lean
- Vendor-backed PICA measurements are reported descriptively for context only; they do not discharge theorem obligations or establish interaction effects
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

Data-driven figures are regenerated with `python3 scripts/make_paper_figures.py`.

Canonical outputs:

- `paper/build/main.pdf`
- `paper/build/main_flattened.tex`
