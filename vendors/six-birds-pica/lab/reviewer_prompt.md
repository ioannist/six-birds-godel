# Reviewer Prompt: Six Birds Emergence Ladder — Phase 2 Audit

## Your Role

You are a scientific code reviewer. Your job is to **prepare a review plan** — a numbered list of tickets that, when completed, will verify every claim this project makes.

This is the PLANNING step only. You are producing an overview of each ticket with enough context to understand its purpose and scope. In later steps, you will be asked to **flesh out each ticket** one at a time with full detail (exact files, line ranges, commands, pass/fail criteria). After that, a separate implementer will execute each fleshed-out ticket.

For now, each ticket needs all of the following, but at summary level (not line-by-line detail — that comes when you flesh out each ticket individually in later steps):

1. **Title** — what to check or fix (short)
2. **Rationale** — why this matters for scientific validity (1-2 sentences)
3. **Scope** — which files/functions/claims are involved (high-level)
4. **Approach** — what kind of work is needed (code reading, running tests, writing a diagnostic script, parsing logs, etc.)
5. **Pass criteria** — what "pass" looks like in summary (e.g., "frob formula matches ||M - 1*pi'||_F", "no NaN/Inf in any sweep log", "σ=0 is confirmed by independent computation on a known non-reversible kernel")
6. **Risk if skipped** — what could be wrong if we don't check this

---

## What This Project Does

This project studies **emergent coarse-graining** from 6 algebraic primitives (P1-P6) applied iteratively to random Markov kernels. The core claim is:

> Starting from ANY random dense Markov kernel (fast-mixing, featureless), iteratively applying P1-P6 creates slow-mixing bottleneck structure that supports non-trivial macro kernels at 3 levels of coarse-graining, with the macro processes remaining Markov and the result being scale-independent (n=32 to n=256).

All structure must emerge from the primitives — no engineered substrates, no external physics.

## Architecture

- **Micro kernel**: `MarkovKernel::random(n, seed)` — dense random transition matrix
- **Dynamics**: iterative P1 (row perturbation) + P2 (edge gating, spectral-guided) + P3 (protocol phase) + P6 (budget drive), with P4 (spectral partition) as observation lens and P5 (viability) as constraint
- **Observation**: spectral partition (sign patterns of top-k eigenvectors) defines macro states, K^tau gives the macro kernel, tau adaptive from spectral gap
- **Ladder**: L0 dynamics (k=8 partition) → 4-5 state macro → L1 static partition (k=4) → 3-4 state macro → L2 static bisection (k=2) → 2-state macro

## Key Files

| File | Lines | Purpose |
|------|-------|---------|
| `crates/runner/src/main.rs` | 7892 | All experiment implementations (EXP-073..094) |
| `crates/dynamics/src/mixture.rs` | 415 | Core dynamics loop (P1-P6 mixture kernel) |
| `crates/dynamics/src/observe.rs` | 210 | Macro kernel extraction, frob measurement, adaptive tau |
| `crates/dynamics/src/spectral.rs` | 212 | Eigenvector computation, k-way partition, eigenvalue extraction |
| `crates/dynamics/src/state.rs` | 207 | AugmentedState, DynamicsConfig |
| `crates/dynamics/src/viability.rs` | 76 | Kernel viability checks |
| `crates/dynamics/src/drive.rs` | 71 | P6 budget ledger |
| `crates/dynamics/src/protocol.rs` | 71 | P3 phase biasing |
| `crates/six_primitives_core/src/substrate.rs` | 513 | MarkovKernel (random, step, spectral gap, stationary) |
| `crates/six_primitives_core/src/primitives.rs` | 228 | P1-P6 primitive definitions |
| `crates/six_primitives_core/src/helpers.rs` | 325 | Metrics: MI, route mismatch, path asymmetry, etc. |
| `lab/reengineering_notebook.md` | 851 | Master narrative with all results |
| `lab/ledger/closures.jsonl` | 24 | 23 closures (CLO-080..CLO-102) |
| `lab/ledger/experiments.jsonl` | 23 | 22 experiments (EXP-073..EXP-094) |
| `lab/ledger/hypotheses.jsonl` | 24 | 23 hypotheses (HYP-100..HYP-122) |
| `lab/sweeps/sweep_exp*.log` | varies | Raw output from all experiment sweeps |

## Claimed Results (What You Need to Verify)

### POSITIVE claims (should be confirmed as genuine)

1. **Scale-independent non-rank-1 macro structure** (EXP-080): frob ≈ 0.858 for k=2, ≈1.4 for k=4, ≈1.7 for k=8 — does not decay with n (32..256). The frob metric measures Frobenius distance from the nearest rank-1 matrix.

2. **Three-level emergence ladder** (EXP-090): L0→L1→L2 all non-rank-1 with frob > 0.1 in 29/30 runs. Structure propagates through recursive coarse-graining.

3. **Near-Markov macro processes** (EXP-083/086/091): Non-Markovianity < 10^-4 at L0, < 10^-5 at L1. The spectral-guided partition creates near-lumpable structure.

4. **Budget cap has no effect** (EXP-081): attractor identical with/without cap.

5. **Coupling strength has no effect** (EXP-092): frob unchanged across {0,1,2,5,10,20}.

6. **Clean null baseline** (EXP-076): zero modifications, frob = noise when P6 is off.

7. **Temporal MI > 0** (EXP-094): MI = 0.63-0.69 nats at L0 for "block mode" runs (5/10 seeds), exactly 0 for "non-block mode" runs.

8. **Rich spectral eigenvalues** (EXP-094): 2-3 non-trivial eigenvalues at L0 macro kernel for ALL seeds. Two regimes: block mode (λ₂≈1) and spread spectrum.

9. **Route mismatch gradient** (EXP-094): RM increases monotonically through the ladder (L0 < L1 < L2).

10. **Bimodal attractor** (EXP-093): ~50/50 split between balanced partitions (high entropy) and degenerate partitions (low entropy). Frob is high in both modes.

### NEGATIVE claims (should be confirmed as genuinely absent, not a bug)

11. **Chirality σ ≈ 0** at all levels (EXP-094): macro kernels satisfy detailed balance despite P6 micro driving. This means the arrow-of-time does NOT propagate to the macro level.

12. **1D spectral locality = 0** (EXP-094): eigenvector ordering interleaves blocks for small-n macro kernels. No spatial structure emerges.

13. **DPI cascade vacuous** (EXP-094): since σ ≈ 0 at all levels, the inequality σ_L0 ≥ σ_L1 ≥ σ_L2 is trivially satisfied.

---

## Specific Concerns for the Review

### A. Correctness of the frob metric

The frob metric is THE central quantity. It measures how far a macro kernel is from rank-1. Verify:
- The definition in `observe.rs` (look for `frob_from_rank1` or similar)
- That it correctly computes ||M - 1*pi'||_F where pi is the stationary distribution
- That the macro kernel M is correctly constructed from K^tau and the partition
- That adaptive tau (from spectral gap) is computed correctly
- Edge case: when macro_n < k (some clusters empty), does the code handle this?

### B. Correctness of the eigenvector computation

The spectral partition is the observation lens. Everything downstream depends on it:
- `top_eigenvectors()` in `spectral.rs` uses deflated power iteration — verify convergence
- `spectral_partition()` uses sign patterns — verify the mapping
- Are the eigenvectors of K^T (left eigenvectors) or K (right)? For Markov kernels, the stationary distribution is the left eigenvector of K with eigenvalue 1, and we want right eigenvectors for spectral clustering. Verify which one `kernel.step()` implements.

### C. The near-Markov claim

Non-Markovianity < 10^-4 is a strong claim. Verify:
- How is the NM test implemented? (look for `nm_mean`, `nm_max` computation in the experiment code)
- Is the trajectory long enough (200,000 steps)?
- Is the NM test comparing the right distributions?

### D. Chirality σ = 0 — genuine or implementation bug?

`path_reversal_asymmetry()` was a Phase 1 function. Verify:
- The definition in `substrate.rs` or `helpers.rs`
- That it correctly computes Σ_ij π_i K_ij log(π_i K_ij / π_j K_ji) or equivalent
- That it's being called with the correct macro kernel and stationary distribution
- Could rounding issues make a genuinely non-zero σ appear as zero?

### E. MI = 0 for "non-block" mode — genuine or bug?

Temporal MI is computed via `compute_mi()`. Verify:
- The implementation computes H(X_t) + H(X_{t+1}) - H(X_t, X_{t+1}) or equivalent
- For a 4-5 state macro kernel with non-identical rows, MI should be > 0 unless the stationary distribution is concentrated on a single state
- Check whether MI = 0 is because π is concentrated (genuine) or because of a computation error

### F. Locality = 0 — genuine or bug?

`spectral_locality()` was added in EXP-094. Verify:
- For a 4-state macro kernel, the 2nd eigenvector defines an ordering — check that it's non-degenerate
- For n=4, there are at most 3 "neighbor" pairs in the eigenvector ordering. Check whether the transition matrix actually puts weight on these neighbors
- Could the result be an artifact of how small-n kernels work (every state transitions to every other state)?

### G. Scale-independence — is it robust or an artifact?

The frob values at n=32, 64, 128, 256 are claimed to be scale-independent. But:
- At L0, the partition always produces 4-5 macro states regardless of n. Is this because the dynamics converge to the same qualitative structure?
- Could the dynamics be "trapped" by the k=8 partition ceiling?
- Is there a risk that the observed structure is an artifact of the partition method rather than genuine macro structure?

### H. Sweep log integrity

Raw sweep logs are in `lab/sweeps/`. For the key experiments:
- Parse the KEY lines and verify they match the claims in the closures
- Check for anomalies (NaN, Inf, negative frob, etc.)
- Verify sample sizes match claims (e.g., "30 runs" = 10 seeds × 3 scales)

### I. Code-data consistency

- Do the experiment implementations match the parameter descriptions in the ledger?
- Are the sweep logs from the current code, or from a previous version?
- Does `cargo build --release` still compile cleanly?

### J. Markov kernel invariants

After dynamics, the evolved kernel must still be a valid Markov kernel:
- Rows sum to 1
- All entries non-negative
- Check this is verified somewhere in the code

---

## How to Prepare the Plan

1. Read the key source files listed above to understand the implementation
2. Read a sample of sweep logs to understand the output format
3. For each concern (A-J), decide whether it warrants a ticket
4. Add any additional tickets you identify during exploration
5. Order tickets by criticality (correctness of core metrics first, then secondary claims)

Keep tickets focused and atomic — one concern per ticket. The plan should be a concise overview, not a detailed specification.

## Workflow (3 phases)

1. **You (now) — PLAN:** Read the codebase, understand the claims, and reply with the ticket plan directly in your response. Do NOT create or write any files — you have read-only access to the repo. Just output the plan as text.
2. **You (later) — DETAIL:** You will be asked to flesh out each ticket one at a time. For each, you will reply with: exact files/line ranges to inspect, exact commands to run, concrete pass/fail criteria, and what to report back.
3. **Implementer (after that) — EXECUTE:** A separate implementer receives each fleshed-out ticket and executes it. They report back results. If a ticket reveals a bug, a fix ticket is added and executed before proceeding.

The end goal is a robust repo where every positive claim is verified correct and every negative claim is confirmed as genuine (not a bug).
