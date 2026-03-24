//! Commutator diagnostics: measure non-commutativity of primitive pairs.
//!
//! [Pi, Pj] = ||Pi(Pj(K)) - Pj(Pi(K))||_F
//!
//! Non-zero commutator means the order of application matters.
//! This is itself a P3 diagnostic (route mismatch of the primitive pair).
//!
//! ## Why only 3 of 15 commutator pairs
//!
//! There are C(6,2) = 15 unordered pairs of primitives. We implement three:
//!
//! - **[P1, P2]** (S3): The only pair of *action* primitives that both modify K.
//!   Measures whether rewriting-then-gating differs from gating-then-rewriting.
//!   This is the most physically meaningful commutator.
//!
//! - **[P1, P4]** (S4): Action vs diagnostic. Measures whether P1 changes the
//!   partition — i.e., whether rewriting is "partition-breaking".
//!
//! - **[P2, P4]** (S5): Action vs diagnostic. Measures whether gating changes the
//!   partition — i.e., whether edge deletion reshapes sector boundaries.
//!
//! The remaining 12 pairs are omitted for documented reasons:
//!
//! - **P3 pairs** ([P1,P3], [P2,P3], [P3,P4], [P3,P5], [P3,P6]): P3 (holonomy/
//!   route mismatch) is a *read-only diagnostic* on K — it doesn't transform K.
//!   Its commutator with any action primitive is trivially zero because P3(K) = K.
//!   The non-trivial content (does RM change after P1/P2?) is already captured by
//!   the Group B diagnostic cells (B1-B3).
//!
//! - **P5 pairs** ([P1,P5], [P2,P5], [P4,P5], [P5,P6]): P5 (packaging) is
//!   idempotent and read-only (e(e(x)) = e(x)). Same reasoning as P3.
//!
//! - **P6 pairs** ([P1,P6], [P2,P6], [P4,P6]): P6 (audit) is read-only.
//!   Commuting with it just measures "does measuring before vs after matter?"
//!   which is always zero. The non-trivial P6 content (budget, EP) feeds into
//!   the action cells (A6, A12, A13) rather than commutators.
//!
//! - **[P4, P5]**: Both are read-only diagnostics; commutator is trivially zero.
//!
//! ## Sequential compositions (S1, S2)
//!
//! The plan also defined S1 (P1 then P2) and S2 (P2 then P1) as separate
//! diagnostics. These are captured by the commutator: [P1,P2] = ||S1 - S2||_F.
//! The individual compositions S1 and S2 are the evolved kernels themselves, which
//! are already recorded in the sweep output as macro kernel entries.

use six_primitives_core::primitives;
use six_primitives_core::substrate::MarkovKernel;

/// Compute the Frobenius commutator of two kernel transformations.
/// Returns ||f(g(K)) - g(f(K))||_F.
fn commutator_frob(
    kernel: &MarkovKernel,
    f: &dyn Fn(&MarkovKernel) -> MarkovKernel,
    g: &dyn Fn(&MarkovKernel) -> MarkovKernel,
) -> f64 {
    let fg = f(&g(kernel));
    let gf = g(&f(kernel));
    let n = kernel.n;
    let mut sum_sq = 0.0;
    for i in 0..n {
        for j in 0..n {
            let diff = fg.kernel[i][j] - gf.kernel[i][j];
            sum_sq += diff * diff;
        }
    }
    sum_sq.sqrt()
}

/// S3: [P1, P2] commutator — does rewriting before vs after gating matter?
pub fn commutator_p1_p2(kernel: &MarkovKernel, seed: u64) -> f64 {
    let p1 = |k: &MarkovKernel| -> MarkovKernel { primitives::p1_random_perturb(k, 0.1, seed) };
    let mask = vec![vec![true; kernel.n]; kernel.n];
    let p2 = |k: &MarkovKernel| -> MarkovKernel {
        let mut m = mask.clone();
        // Gate a few random edges deterministically based on seed
        let n = k.n;
        for idx in 0..(n / 4) {
            let i = (seed as usize + idx * 7) % n;
            let j = (seed as usize + idx * 13 + 1) % n;
            if i != j {
                m[i][j] = false;
            }
        }
        primitives::p2_gate(k, &m)
    };
    commutator_frob(kernel, &p1, &p2)
}

/// S4: [P1, P4] commutator — does rewriting before vs after partition matter?
/// Since P4 is diagnostic-only, this measures whether P1 changes the partition.
pub fn commutator_p1_p4(kernel: &MarkovKernel, seed: u64) -> f64 {
    let k_rewritten = primitives::p1_random_perturb(kernel, 0.1, seed);
    let part_before = primitives::p4_sectors(kernel);
    let part_after = primitives::p4_sectors(&k_rewritten);

    // Measure partition difference as fraction of states that changed sector
    let n = kernel.n;
    let mut changed = 0;
    for i in 0..n {
        if part_before[i] != part_after[i] {
            changed += 1;
        }
    }
    changed as f64 / n as f64
}

/// S5: [P2, P4] commutator — does gating before vs after partition matter?
pub fn commutator_p2_p4(kernel: &MarkovKernel, seed: u64) -> f64 {
    let n = kernel.n;
    // Create a deterministic gate mask
    let mut mask = vec![vec![true; n]; n];
    for idx in 0..(n / 4) {
        let i = (seed as usize + idx * 7) % n;
        let j = (seed as usize + idx * 13 + 1) % n;
        if i != j {
            mask[i][j] = false;
        }
    }

    let k_gated = primitives::p2_gate(kernel, &mask);
    let part_before = primitives::p4_sectors(kernel);
    let part_after = primitives::p4_sectors(&k_gated);

    let mut changed = 0;
    for i in 0..n {
        if part_before[i] != part_after[i] {
            changed += 1;
        }
    }
    changed as f64 / n as f64
}

/// Compute all commutator diagnostics for a kernel.
pub fn all_commutators(kernel: &MarkovKernel, seed: u64) -> Vec<(&'static str, f64)> {
    vec![
        ("[P1,P2]", commutator_p1_p2(kernel, seed)),
        ("[P1,P4]", commutator_p1_p4(kernel, seed)),
        ("[P2,P4]", commutator_p2_p4(kernel, seed)),
    ]
}
