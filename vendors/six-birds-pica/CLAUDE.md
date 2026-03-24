# Six Birds Emergence Ladder — Operating Manual

## What This Repo Does

This repository implements a **code-first scientific discovery process** studying
emergent coarse-graining from ONLY the six primitives P1-P6 ("Six Birds") applied
to random Markov kernels.

**Current phase: Re-engineering** — replacing the static algebraic cascade with a
dynamical system that includes P6 drive, fast-slow separation, and cross-layer coupling.
See `lab/reengineering_notebook.md` for the full plan.

**Phase 1** (71 experiments, 16 layers, 69 closures) is archived in git history.
Key finding: exact computation revealed all macro kernels are rank-1 under the static
cascade. The architecture must change, not the parameters.

## Non-Negotiable Rules

1. **Only axioms: P1-P6** and the minimal substrate as defined in `theory/primitives.yaml`.
2. **No external physics or math facts** as assumptions. Generic programming constructs
   (arrays, graphs, RNG, hashing) are fine, but meaning (geometry, counting, fields, etc.)
   must be treated as emergent hypotheses justified by experiments.
3. **Everything is code.** All claims must be testable. Every accepted claim needs:
   experiment ID(s), parameter sweep, metrics, reproducibility (seeded), artifacts in repo.
4. **Ledger discipline.** Every hypothesis/experiment/result/closure is recorded in
   `lab/ledger/` (machine-readable JSONL).
5. **Iterate small.** Prefer the smallest runnable experiment that could falsify a hypothesis.
6. **Don't rewrite `research/`.** Treat it as read-only input.

## Protocol-Compliant Operations

These are legitimate uses of P1-P6 (confirmed during re-engineering review):
- **P6 as drive** (not just diagnostic): EP, budget ledger, defect-maintenance
- **Mixture kernel**: stochastic choice among P1-P6 per step
- **Active P3**: internal protocol phase as state variable
- **Cross-layer coupling as P2 feasibility restriction**: upper level constrains lower
- **Adaptive tau**: set by formula from kernel spectral properties

## How to Run Experiments

```bash
cargo build --release
cargo run --release -p runner -- --exp EXP-073 --sweep --scales 32,64,128,256
```

## Where Results Go

```
lab/
  ledger/
    hypotheses.jsonl    # Phase 2 hypotheses (HYP-100+)
    experiments.jsonl    # Phase 2 experiments (EXP-073+)
    results.jsonl        # Phase 2 run results
    closures.jsonl       # Phase 2 closures
    SCHEMA.md            # JSONL schemas
  sweeps/               # Sweep output logs
  reengineering_notebook.md  # Master plan for Phase 2
```

## Technology

- **Rust** (`crates/`): Core simulation engine, experiment runner.
- **Python** (`analysis/`, `scripts/`): Analysis and plotting.
- **theory/**: Canonical primitive spec (`primitives.md`, `primitives.yaml`).
- **skills/**: Process handbook for operating in this repo.

## ID Conventions

- Hypothesis: `HYP-###` (Phase 2 starts at HYP-100)
- Experiment: `EXP-###` (Phase 2 starts at EXP-073)
- Result run: `RUN-<exp>-<seed>-<scale>-<hash>`
- Closure: `CLO-###`
