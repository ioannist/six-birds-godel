# Noether Modes: Post-Review Implementation Notes

**Status: IMPLEMENTED.** New probes added to codebase per reviewer guidance.

# Reviewer Request: Detecting Emergent Conservation Laws in Coarse-Grained Markov Chains

## Context

We study emergent structure from applying 6 primitives (P1-P6) to random Markov kernels.
After running dynamics (kernel mutations, gating, budget), we coarse-grain to k-state
macro kernels and ask: **does the macro chain exhibit emergent "physics"?**

We have 5 Lagrange probes that measure different aspects of emergent lawfulness.
Four of them produce meaningful signals. The fifth — `noether_modes` — is nearly universally
zero across 2,486 measurements (rare nonzero at small n, e.g., A14_only n=32 k=5/k=8).
We think the detection logic is wrong, not the phenomenon.

## What noether_modes Did (REMOVED from codebase)

The old function (removed after review — replaced by spectral conservation probes below):

```rust
/// Count eigenvalues with |lambda| >= 1 - eps, excluding lambda_1 = 1.
pub fn noether_modes(eigenvalues: &[f64], eps: f64) -> usize {
    eigenvalues.iter().skip(1)
        .filter(|&&lam| lam.abs() >= 1.0 - eps)
        .count()
}
```

It was called with `eps = 0.05` on eigenvalues of the **symmetrized similarity matrix** S:
1. Build time-reversal: K*_{ij} = pi_j K_{ji} / pi_i
2. Symmetrize: K_sym = (K + K*) / 2
3. Similarity transform: S_{ij} = sqrt(pi_i) * K_sym_{ij} / sqrt(pi_j)
4. Jacobi eigendecomposition of S

## The Problem: Actual Eigenvalue Spectra

We ran a diagnostic dumping full eigenvalue spectra across 4 PICA configs × 3 scales:

```
config            k   lam_2      lam_3    gap_ratio    frob     sigma
---------------------------------------------------------------------
baseline          4   0.038      0.002     0.962      0.129    0.020
baseline          8   0.083      0.061     0.917      0.191    0.127
baseline         16   0.100      0.078     0.900      0.311    0.566
full_action       4   0.452      0.074     0.144      0.093    0.018  <-- OUTLIER
full_action       8   0.078      0.049     0.922      0.163    0.118
full_action      16   0.098      0.088     0.897      0.244    0.413
A14_only          4   0.273     -0.006     0.578      0.104    0.013  <-- REDUCED GAP
A14_only         16   0.098      0.092     0.902      0.327    0.842
A19_only          4   0.079      0.020     0.920      0.089    0.008
A19_only         16   0.095      0.077     0.904      0.316    1.577
```

**Largest lambda_2 ever observed: 0.452** (full_action, k=4). The threshold for
eps=0.05 requires |lambda| >= 0.95. Even eps=0.50 (requiring |lambda| >= 0.50)
would catch almost nothing.

The macro kernels are fast-mixing: all nontrivial eigenvalues decay rapidly.
Coarse-graining averages away slow dynamics. **Asking "is any eigenvalue near 1?"
is the wrong question for these systems.**

## What IS Different

Despite noether_modes being nearly always 0 (rare nonzero at small n), there IS meaningful spectral structure:

1. **Spectral gap ratio varies 50x**: full_action@k=4 has gap_ratio=0.144 vs
   baseline's 0.962. This means lambda_2 is close to lambda_1 — two modes of
   comparable importance, suggesting a quasi-conserved partition.

2. **The other Lagrange probes detect real signals**:
   - `pla2_gap`: anti-correlates with frob (r=-0.727). Strongest single predictor.
   - `step_entropy`: r=-0.653. full_action is qualitatively different (0.793 vs ~1.1).
   - `diff_alpha`: r=+0.602. Anomalous diffusion exponents emerge.
   - `geo_r2`: Two universality classes — geometric (A14, increasing) vs non-geometric (full_action, ~0).

3. **Two emergent physics flavors** already identified:
   - **Geometric**: A14-driven partition competition → geo_r2 increases with k, action is spatial
   - **Thermodynamic**: full_action → deterministic transitions, broken PLA2, reduced entropy

## What We'd Like Help With

### Q1: Is "eigenvalue near 1" the right concept for stochastic conservation laws?

In continuous-time Hamiltonian systems, Noether's theorem gives exact conservation
from continuous symmetries. In discrete-time Markov chains:

- Are approximate conservation laws better detected by **spectral gap structure**
  (clusters of eigenvalues separated by gaps) rather than absolute proximity to 1?
- Should we look at the **ratio** lambda_2/lambda_1 rather than |lambda_2 - 1|?
- Is there a well-known stochastic analog of Noether's theorem we should reference?

### Q2: What should replace the current probe?

Given our eigenvalue spectra, we're considering these alternatives:

**(a) Spectral gap ratio**: `gap_ratio = (lam_1 - lam_2) / lam_1`
- Already computed, shows 50x variation between configs
- But: it's a single number, doesn't count "how many" conserved quantities

**(b) Eigenvalue entropy**: `H = -sum_i (|lam_i|/Z) * ln(|lam_i|/Z)` where Z = sum|lam_i|
- Higher entropy → more modes contribute equally → richer dynamics
- Captures the "shape" of the spectrum, not just the gap

**(c) Number of eigenvalues above median**: `count(|lam_i| > median(|lam|))`
- Relative threshold, adapts to the kernel's mixing rate
- But: always approximately k/2 by definition, may not discriminate

**(d) Spectral cluster count**: Count clusters in the eigenvalue spectrum using
a gap-detection heuristic (e.g., gaps larger than some multiple of mean spacing)
- Maps directly to "number of approximately independent slow manifolds"
- Requires choosing the gap multiplier

**(e) Left-eigenvector approach**: Instead of eigenvalues of the symmetrized matrix,
look at left eigenvectors of K directly. A conservation law pi^T f = const maps
to a left eigenvector with eigenvalue 1.
- More physically motivated
- But: for stochastic matrices, the only exact left eigenvector with lambda=1
  is pi itself (the stationary distribution), which is always there.

### Q3: Should we probe the micro kernel instead?

The macro kernel is obtained by coarse-graining (averaging transition probabilities
within clusters). This averaging naturally destroys slow modes. Perhaps we should:
- Compute eigenvalues of the **micro** kernel K (n=32..256) after dynamics
- Look for slow modes there, and track how they map to the macro partition
- Count how many micro slow modes are "preserved" vs "lost" under coarse-graining

### Q4: Is the spectral gap ratio itself the conservation law signal?

Looking at the data: full_action at k=4 has gap_ratio=0.144 (lambda_2=0.452,
close to lambda_1=0.528). In block-diagonal Markov chains, each block contributes
an eigenvalue near 1. A gap_ratio near 0 would indicate near-block-diagonal structure
(= strong conservation of block membership).

- Is the gap_ratio essentially measuring "how conserved is the partition?"
- If so, it's already the right probe, just not framed as "noether_modes"
- Would reframing it as "partition conservation index = 1 - gap_ratio" be more
  interpretable?

### Q5: Literature pointers?

Any references for:
- Stochastic analogs of Noether's theorem (we're aware of the general concept
  but not specific detection methods for Markov chains)
- Spectral methods for detecting quasi-conservation laws in discrete systems
- "Emergent conservation" in coarse-grained stochastic processes
- Eigenvalue-based diagnostics for Markov chain structure beyond the standard
  spectral gap

---

## Reviewer Response & Implementation

### Reviewer Guidance (2026-02-24)

1. **Use relative slow-mode count**: |lambda_i| / |lambda_2| >= r (r = 0.5, 0.7, 0.9)
2. **Use spectral participation** (effective mode count) from nontrivial eigenvalues
3. **Use eigenvalue entropy** over nontrivial spectrum
4. **Use gap-structure metrics** (gap-ratio style signal)
5. **Report t_rel = 1/(1-|lambda_2|)**, not hard-thresholded counts
6. **On Q4**: yes, gap-ratio IS the conservation-law proxy, better than absolute counting
7. **On Q3**: do both micro and macro
8. **Literature**: Levin/Peres/Wilmer (spectral gap), Coifman et al. (diffusion maps),
   Nüske et al. (variational transfer operators), PCCA+ (nonreversible metastable decomp)

### Implementation (same day)

**New functions in `lagrange.rs`:**
- `relaxation_time(eigenvalues)` → t_rel = 1/(1-|lambda_2|)
- `spectral_gap_ratio(eigenvalues)` → (lambda_1 - |lambda_2|) / lambda_1
- `eigenvalue_entropy(eigenvalues)` → H = -sum p_i ln(p_i) over nontrivial spectrum
- `spectral_participation(eigenvalues)` → N_eff = 1/sum(p_i^2) (inverse participation ratio)
- `relative_slow_modes(eigenvalues, r)` → count with |lambda_i|/|lambda_2| >= r
- `nontrivial_eigenvalues(eigenvalues)` → full nontrivial spectrum for post-hoc analysis

**New fields in `ScaleScanEntry`:**
- `t_rel`, `gap_ratio`, `eigen_entropy`, `spectral_participation`
- `slow_modes_r50`, `slow_modes_r70`, `slow_modes_r90`
- `nontrivial_eigenvalues` (full spectrum vector for post-hoc)

**New fields in `AuditRecord` (micro-kernel):**
- `micro_t_rel`, `micro_gap_ratio`, `micro_eigen_entropy`, `micro_spectral_participation`
- `micro_top_eigenvalues` (top 5 nontrivial, sorted descending)

### Validation Results (n=32, seed=42)

**Macro probes now discriminate** (old noether_modes: nearly always zero, uninformative):

```
config            k  a_k    lam_2    gap_r    t_rel    N_eff  H_eig    r50    r70    r90
baseline          4    4   0.0375   0.9625    1.039    2.081  0.778      2      2      2
full_action       4    4   0.4518   0.1442    1.824    1.515  0.632      1      1      1
A14_only          4    4   0.2733   0.5779    1.376    1.476  0.558      1      1      1
A19_only          4    4   0.0792   0.9199    1.086    2.425  0.970      2      1      1
```

**gap_ratio variation: 7x** (0.144 vs 0.963). full_action has near-degenerate top-2 eigenvalues.
**t_rel variation: 75%** (1.82 vs 1.04). The slow mode IS detected.

**Micro probes reveal hidden structure:**
```
config            gap_r    t_rel    N_eff    H_eig  top_5_eigenvalues
baseline         0.8668    1.154   21.423    3.183  [0.1387, 0.1332, 0.1215, 0.1161, 0.1126]
A19_only         0.7108    1.282   20.585    3.187  [0.2202, 0.1322, 0.1153, 0.1104, 0.1000]
```

A19_only has micro gap_ratio 0.711 vs 0.867 baseline — **slow structure exists at micro level,
masked by coarse-graining.** Its top eigenvalue (0.220) is 1.6x higher than baseline's (0.139).

### Tests
11 new unit tests + 1 integration test. All 95 tests pass.
