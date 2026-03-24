1. **Build + deterministic reproducibility smoke test**

* **Rationale:** If the project can’t be built and rerun deterministically from seeds, none of the reported sweeps/closures can be trusted as reproducible scientific results.
* **Scope:** Whole repo; `crates/runner` CLI entrypoints; all experiments referenced in `lab/ledger/*.jsonl`.
* **Approach:** `cargo build --release`, `cargo test`; run 1–2 representative experiments twice with the same seed/scale and confirm identical KEY-line outputs (or documented tolerances if floats differ).
* **Pass criteria:** Clean build/test; reruns with identical (seed, scale, exp) reproduce the same macro_n/tau/frob/etc. within a strict tolerance (or bitwise-identical if intended).
* **Risk if skipped:** Logs may be stale, non-reproducible, or dependent on undefined behavior/PRNG differences.

---

2. **Kernel semantics audit: stochastic convention + `step()` orientation (K vs Kᵀ)**

* **Rationale:** Every spectral routine (gap/eigenvectors/partition), stationary distribution computation, and macro construction depends on whether vectors are propagated as row vs column and whether algorithms are using left vs right eigenvectors.
* **Scope:** `crates/six_primitives_core/src/substrate.rs` (`MarkovKernel::step`, `stationary`, `evolve`), `crates/dynamics/src/spectral.rs` (power iteration), `crates/dynamics/src/observe.rs`.
* **Approach:** Code reading + small sanity checks on tiny kernels (2–5 states) where left/right eigenvectors and stationarity are known analytically; verify documentation matches implementation.
* **Pass criteria:** Clear, consistent convention across code: (a) rows sum to 1; (b) `step()` implements the intended multiplication; (c) spectral partition is using the intended eigenvectors for clustering.
* **Risk if skipped:** Spectral partition may be clustering on the “wrong” eigenvectors (or on Kᵀ when K is intended), invalidating all downstream macro claims.

---

3. **Spectral gap correctness + adaptive τ correctness**

* **Rationale:** Adaptive τ defines the macro timescale (`K^τ`). If the gap is miscomputed (e.g., tracking a singular value or yielding negative gaps), τ can collapse to 1 or blow up, artificially creating or destroying macro structure.
* **Scope:** `crates/six_primitives_core/src/substrate.rs` (`spectral_gap`, `spectral_gap_with_eigvec`), `crates/dynamics/src/observe.rs` (`adaptive_tau`), all experiments that log `gap`, `eff_gap`, and/or `tau` (EXP-073, 080–094).
* **Approach:** Compare reported gap against a trusted eigensolver on small matrices (exact eigenvalues of K or Kᵀ as appropriate); check sign/range (should be ≥0 under the project’s definition); verify τ behaves as intended and respects caps.
* **Pass criteria:** For representative kernels (random, near-block, reversible, non-reversible), computed gap matches reference `1 - |λ₂|` (or the project’s formally stated definition) within tolerance; τ is monotone in gap and never silently flips to 1 due to negative/invalid gap.
* **Risk if skipped:** Central claims about “slow-mixing emergent structure” (and all `K^τ` macro kernels) may be artifacts of an incorrect spectral-gap/τ pipeline.

---

4. **Eigenvector computation validity + convergence (deflated power iteration)**

* **Rationale:** The observation lens is spectral sign-partitioning; if eigenvectors don’t converge to the intended modes, partitions (and thus gating decisions and macro kernels) become unreliable.
* **Scope:** `crates/dynamics/src/spectral.rs` (`top_eigenvectors`, `spectral_partition`, `full_eigenvalues`), plus any use of eigenvectors for ordering/locality.
* **Approach:** Code review + diagnostic runs on small kernels: compare returned eigenvectors/eigenvalues to a reference eigendecomposition; test stability across seeds and near-degenerate eigenvalues; verify deflation and Gram–Schmidt logic.
* **Pass criteria:** Returned vectors approximate the intended eigenvectors (or clearly documented alternative) with acceptable residuals `||Kᵀv - λv||`; partitions are stable under small perturbations (or instability is documented/handled).
* **Risk if skipped:** “Emergence” may be driven by numerical artifacts or inconsistent partitions, not genuine dynamics.

---

5. **Spectral sign-partition mapping + empty-cluster handling**

* **Rationale:** Many claims rely on “k=4 gives 3 macro states” and “k=8 gives 4–5 macro states.” This hinges on correct sign-binning and correct handling of empty quadrants.
* **Scope:** `crates/dynamics/src/spectral.rs` (`spectral_partition`, renumbering of used clusters), `crates/dynamics/src/observe.rs` (macro_n logic), EXP-082/084/085/090/094.
* **Approach:** Construct controlled eigenvector sign-pattern examples; verify mapping, renumbering, and macro_n; confirm no silent cluster drops that bias metrics.
* **Pass criteria:** Partition mapping matches the documented sign-pattern rule; macro_n equals number of non-empty sign bins; no downstream code assumes macro_n==k.
* **Risk if skipped:** Reported “macro_n” regimes and ladder branching may be bookkeeping artifacts.

---

6. **Macro kernel construction from `K^τ` + lens definition audit**

* **Rationale:** The macro kernel M must be computed exactly as claimed (“K^τ gives the macro kernel”) and must correspond to the stated coarse-graining rule (uniform vs stationary-weighted averaging matters scientifically).
* **Scope:** `crates/six_primitives_core/src/helpers.rs` (`matrix_power`, `build_macro_from_ktau`, `build_induced_macro_kernel`), `crates/dynamics/src/observe.rs` (how these are invoked), EXP-073 and all Phase 2 experiments.
* **Approach:** Independent reconstruction on small matrices: compute `K^τ` explicitly, aggregate using the implemented lens rule, and confirm the macro kernel matches; test both uniform and stationary-weighted aggregation to ensure the project uses the intended one.
* **Pass criteria:** Macro kernel entries match the formally specified construction; macro kernel is row-stochastic; edge cases (tiny clusters, tau=1, large tau cap) behave predictably.
* **Risk if skipped:** The central object being measured (macro kernel) may not be the one the narrative claims.

---

7. **Stationary distribution computation accuracy (micro + macro)**

* **Rationale:** Stationary π is used in frob, MI, σ, and sometimes deflation. In slow-mixing regimes, a fixed-iteration power method can return a biased π.
* **Scope:** `crates/six_primitives_core/src/substrate.rs` (`stationary`), any code using π (observe metrics, MI, σ).
* **Approach:** Compare π from `stationary()` to a reference solution (solve πK=π with normalization) on small kernels; test worst-case slow-mixing macro kernels (tiny gap) and verify convergence diagnostics.
* **Pass criteria:** π is accurate enough that downstream metrics are stable (changes in π within tolerance don’t materially change frob/MI/σ conclusions); non-convergence is detected or mitigated.
* **Risk if skipped:** Metrics can be systematically wrong in exactly the emergent slow-mixing regime the project emphasizes.

---

8. **Frobenius-from-rank-1 metric correctness (project’s central quantity)**

* **Rationale:** The frob metric is the flagship measurement. Any bug or mismatch in definition invalidates nearly every “non-rank-1 macro structure” claim.
* **Scope:** `crates/dynamics/src/observe.rs` (`frob_from_rank1`), manual frob computations embedded in experiments (e.g., EXP-073), narrative references in `lab/reengineering_notebook.md`.
* **Approach:** Verify formula matches the stated `||M - 1·πᵀ||_F` with π the stationary distribution of M; cross-check against an independent implementation on test matrices (rank-1, near-rank-1, block-diagonal).
* **Pass criteria:** Frob is ~0 for true rank-1 kernels; scales correctly with controlled perturbations; matches independent computation to tight tolerance.
* **Risk if skipped:** Reported frob plateaus (e.g., ~0.858, ~1.4, ~1.7) could be measurement artifacts.

---

9. **Markov kernel invariants + viability constraint audit**

* **Rationale:** The dynamics claim “no engineered substrate” and must keep kernels valid Markov kernels. If kernels drift (negative entries, row sums ≠1), spectral and macro computations become meaningless.
* **Scope:** `crates/six_primitives_core/src/primitives.rs` (P1/P2 transforms), `crates/dynamics/src/viability.rs`, `crates/dynamics/src/mixture.rs` (accept/reject logic), `substrate.rs` utilities (`block_count`, entropy).
* **Approach:** Assert invariants after every accepted step in a diagnostic run; check viability thresholds vs intended meaning; confirm rejected proposals don’t leak into state.
* **Pass criteria:** Every accepted kernel is row-stochastic within tolerance; all entries ≥0; viability checks match the intended constraints (connectedness, no-absorbing, entropy floor).
* **Risk if skipped:** Emergent structure could be produced by invalid kernels or by unintended constraint loopholes.

---

10. **Non-Markovianity metric implementation audit (TV distance estimator)**

* **Rationale:** Claims like “non-Markovianity < 1e-4” are extremely strong and sensitive to estimator bias, excluded pairs, and sampling noise.
* **Scope:** Non-Markov code in `crates/runner/src/main.rs` (EXP-074, EXP-083, EXP-086, EXP-091), any helper used for counts/TV.
* **Approach:** Review estimator definitions; verify min-count filtering isn’t hiding rare but important transitions; run synthetic known non-lumpable chains to ensure estimator detects memory; quantify expected sampling noise for 200k steps.
* **Pass criteria:** NM estimates match known ground-truth behavior on controlled examples; reported tiny NM values occur only when macro dynamics are provably (near-)lumpable and n_pairs is sufficiently large.
* **Risk if skipped:** “Near-Markov macro process” may be a statistical artifact of the test rather than a real property.

---

11. **Chirality/σ (entropy production) formula + numerical stability audit**

* **Rationale:** The negative claim “σ≈0 everywhere” is scientifically delicate: σ can vanish due to a real reversibility property or due to a formula/implementation error (missing π factors, mishandled zeros).
* **Scope:** `crates/six_primitives_core/src/substrate.rs` (path reversal / entropy production function), EXP-094 reporting, any σ usage in earlier experiments (EXP-073 root σ).
* **Approach:** Validate σ on (a) known reversible chains (should be 0), (b) constructed non-reversible chains (should be >0), (c) random non-reversible chains; confirm correct theoretical expression is implemented (or clearly document the chosen definition).
* **Pass criteria:** σ matches a reference implementation of entropy production per step; returns 0 for reversible kernels and clearly nonzero for non-reversible test cases; reported near-zero σ in EXP-094 persists under the correct formula and higher precision thresholds.
* **Risk if skipped:** The headline “arrow-of-time does not propagate” could be a pure implementation bug.

---

12. **Temporal mutual information metric correctness (MI = I(Xₜ;Xₜ₊₁))**

* **Rationale:** MI is used to argue emergent temporal dependence (block mode) versus vacuity (non-block mode). Any MI bug can invert that conclusion.
* **Scope:** `crates/runner/src/main.rs` (`compute_mi`), EXP-073 and EXP-094 outputs, notebook claims.
* **Approach:** Unit-test MI on analytically solvable cases (rank-1 → MI=0; deterministic periodic chain → MI high; mixed chain → intermediate); verify π and marginals are computed consistently.
* **Pass criteria:** MI matches independent computation to tolerance; MI=0 only when the chain is effectively i.i.d. or occupancy collapses to a single macro state.
* **Risk if skipped:** “MI=0 vs MI≈0.65” bimodality could be a calculation artifact.

---

13. **Spectral eigenvalue reporting (“spectral lines”) audit**

* **Rationale:** Claims about “2–3 non-trivial eigenvalues” and regimes (λ₂≈1 vs spread) require correct eigenvalue computation, not just approximate Rayleigh quotients on potentially wrong vectors.
* **Scope:** `crates/dynamics/src/spectral.rs` (`full_eigenvalues`), EXP-094 logging of `eigs=[...]`, any gap/eigenvalue logic.
* **Approach:** For each logged macro kernel in EXP-094, compute the true spectrum with a trusted method (dense eigensolver) and compare; check ordering and handling of complex eigenvalues.
* **Pass criteria:** Reported eigenvalues match reference values (within tolerance); “block mode” classification based on λ₂ is consistent across methods.
* **Risk if skipped:** The “rich spectrum” claim could be an artifact of an approximate eigen routine.

---

14. **1D spectral locality metric audit**

* **Rationale:** “Locality=0” is a strong negative claim and easy to break by edge-case mistakes (small n, degenerate eigenvectors, ordering ties).
* **Scope:** `crates/dynamics/src/spectral.rs` (`spectral_locality`), EXP-094 `locality` field.
* **Approach:** Validate on synthetic “local” chains (ring/line random walk) where locality should be high; on dense random chains where locality should be low but not necessarily exactly 0; examine tie-breaking and n≤3 behavior.
* **Pass criteria:** Metric returns high values on known local kernels and low values on known non-local kernels; EXP-094 locality values are reproduced by an independent implementation and are not trivially forced to 0 by degeneracy handling.
* **Risk if skipped:** The “no spatial structure emerges” conclusion may be premature or wrong.

---

15. **Route mismatch metric audit + ladder monotonicity check**

* **Rationale:** “RM increases monotonically through the ladder” is a derived claim that depends on consistent definitions across levels and consistent τ choices.
* **Scope:** `crates/six_primitives_core/src/helpers.rs` (`fast_mean_rm`, `mean_route_mismatch`), EXP-094 RM logging, ladder construction code in EXP-090/094.
* **Approach:** Verify RM equals the stated comparison (evolve-then-pushforward vs pushforward-then-macro-step); confirm the “fast” RM is mathematically equivalent to the sampled RM under the chosen distributions; verify monotonicity statistics across seeds.
* **Pass criteria:** RM implementation matches definition; RM values from logs are reproducible; monotonic condition (L0<L1<L2) holds with the stated strength (e.g., all or a quantified fraction).
* **Risk if skipped:** RM gradient may be a bookkeeping artifact of different state spaces or τ choices, not a real emergent trend.

---

16. **Budget ledger + cost model audit (P6)**

* **Rationale:** Claims about “P6 is necessary,” “budget cap has no effect,” and “system is self-sustaining” depend on correct cost computation and correct cap enforcement.
* **Scope:** `crates/dynamics/src/drive.rs` (KL cost, cap/boost), `crates/dynamics/src/mixture.rs` (budget updates and affordability checks), EXP-076/078/080/081.
* **Approach:** Verify cost is computed as intended and is always ≥0; check whether deleting edges has intended cost; confirm budget cap is applied where claimed; confirm P6 actually changes reachable dynamics when enabled.
* **Pass criteria:** Budget and costs evolve exactly as specified; cap binds in capped experiments; “no modification” regimes truly have zero accepted modifications.
* **Risk if skipped:** Null results (or invariances) could come from a broken budget mechanism.

---

17. **Cross-layer coupling mechanism audit (correctness + “no effect” interpretation)**

* **Rationale:** “Coupling strength has no effect” is only meaningful if coupling genuinely alters the acceptance landscape; otherwise it’s a no-op.
* **Scope:** `crates/dynamics/src/mixture.rs` (coupling penalty), EXP-087 and EXP-092 code paths in `crates/runner/src/main.rs`.
* **Approach:** Instrument or log coupling penalty terms on representative runs; verify that strength>0 changes accept/reject rates (as claimed) and that the penalty is applied to the intended moves (boundary-crossing).
* **Pass criteria:** Coupling measurably changes P2 acceptance as a function of strength/interval; yet macro structure metrics remain within stated bounds across strengths.
* **Risk if skipped:** “No effect” may actually mean “coupling never turned on / never applied correctly.”

---

18. **Sweep log integrity + anomaly scan**

* **Rationale:** The ledger/closures are only as reliable as the raw logs. Scientific audits require confirming no NaN/Inf, no impossible values, and correct sample sizes.
* **Scope:** `lab/sweeps/sweep_exp*.log`, `lab/ledger/*.jsonl` (declared sample sizes), KEY-line formats used by `runner`.
* **Approach:** Write/execute a parser to extract KEY lines; validate counts (e.g., 10 seeds × 3 scales = 30 runs); flag NaN/Inf/negative probabilities, negative frob, impossible macro_n, etc.
* **Pass criteria:** Logs parse cleanly; sample sizes match ledger; no numerical/pathology flags; KEY summaries match per-run lines.
* **Risk if skipped:** Reported statistics could be computed from corrupted/partial logs or contain silent numerical failures.

---

19. **Code ↔ ledger ↔ log consistency audit**

* **Rationale:** The audit must ensure each experiment implementation matches the parameters described in the ledger, and that the committed logs correspond to that implementation (not an older version).
* **Scope:** `lab/ledger/experiments.jsonl`, `lab/ledger/closures.jsonl`, `lab/reengineering_notebook.md`, `crates/runner/src/main.rs` experiment functions.
* **Approach:** For each EXP-073..094: cross-check parameter values (n_clusters, cap, tau_alpha, total_steps, etc.) between ledger and code; confirm logs contain the expected KEY fields and match those parameters.
* **Pass criteria:** No mismatches between code parameters and ledger descriptions; any deviations are explicitly documented and justified.
* **Risk if skipped:** You may “verify” the wrong experiment or the wrong configuration.

---

20. **Reproduce Phase 0 baseline: pre-rank-1 τ-regime + fast-mixing roots (EXP-073)**

* **Rationale:** The Phase 2 claims depend on the Phase 0 baseline being correct: dense random kernels should collapse to rank-1 quickly under `K^τ`, and adaptive τ alone should not “fake” emergence.
* **Scope:** EXP-073 implementation and its metrics (frob vs τ, root gaps, MI).
* **Approach:** Rerun EXP-073 across the stated scales (including n=256); recompute summary statistics reported in CLO-080; verify mixing-time interpretation is consistent with correctly computed spectral gaps.
* **Pass criteria:** Frob decays sharply with τ; “τ=1 only” pre-rank-1 window matches closure; root kernels show O(1) mixing by the project’s chosen gap definition.
* **Risk if skipped:** Phase 2 “improvement” might be overstated if the baseline was mis-measured.

---

21. **Reproduce Phase 0 baseline: non-Markovianity bimodality under merge lens (EXP-074)**

* **Rationale:** The project contrasts Phase 1 “memoryful macro” with Phase 2 “near-Markov macro”; the Phase 0 memory finding must be real.
* **Scope:** EXP-074 output (nm_mean/nm_max/macro_n) and CLO-081 claims.
* **Approach:** Rerun EXP-074; verify bimodality and correlation with macro_n; confirm scaling trend with n; confirm estimator isn’t producing bimodality from filtering artifacts.
* **Pass criteria:** Two regimes appear with strong correlation to macro_n; magnitudes align with CLO-081 ranges.
* **Risk if skipped:** Phase 2 “near-Markov” improvement loses context and may be misinterpreted.

---

22. **Reproduce Phase 0 control: min-gap vs max-gap merge equivalence (EXP-075)**

* **Rationale:** This supports the claim that the collapse mechanism is `K^τ` itself, not merge selection heuristics.
* **Scope:** EXP-075 outputs (dev=0 claims) and CLO-082.
* **Approach:** Rerun EXP-075; confirm dev is identically zero (or within strict tolerance) across runs; validate any randomized components are controlled.
* **Pass criteria:** min-gap and max-gap results match in the stated proportion (ideally 39/40 or 80/80 depending on accounting).
* **Risk if skipped:** Subsequent design decisions (moving to Phase 2 dynamics) may be based on a false negative.

---

23. **Reproduce null/activation claims: P6 OFF implies zero modifications (EXP-076 & EXP-078)**

* **Rationale:** The project claims all later emergence requires P6 (budget) to allow any kernel modification.
* **Scope:** EXP-076 (null) and EXP-078 (P3-only) sweeps; CLO-083.
* **Approach:** Rerun both; confirm p1/p2 accepted counts are zero; confirm kernel does not change; confirm frob equals baseline spectral noise and decreases with scale.
* **Pass criteria:** Zero accepted modifications; frob distribution matches “noise” baseline reported.
* **Risk if skipped:** Later “emergence” could be misattributed if modifications are happening unexpectedly in null regimes.

---

24. **Reproduce P6-drive scaling: weak structure + decay with n (EXP-077 & EXP-079)**

* **Rationale:** These experiments establish why spectral-guided gating is needed for scale-independence; they also validate the P6+P3 architecture before adding guidance.
* **Scope:** EXP-077 (P6 only), EXP-079 (P6+P3), CLO-084–086.
* **Approach:** Rerun and recompute max_frob vs scale; verify accept rates and eff_gap shifts; confirm claimed amplification of P3 over P6-only.
* **Pass criteria:** max_frob magnitudes and scale-decay match closures; P3 provides modest uplift and reduced accept rates.
* **Risk if skipped:** The motivation for the key Phase 2 mechanism (spectral-guided P2) is not actually demonstrated.

---

25. **Reproduce core Phase 2 claim: scale-independent 2-state attractor (EXP-080), including n=256**

* **Rationale:** This is the central positive claim: emergence of slow-mixing structure and non-rank-1 macro kernels that do not decay with scale.
* **Scope:** EXP-080 implementation, CLO-087, and the prompt’s claim (n=32..256, frob≈0.858 for k=2).
* **Approach:** Rerun EXP-080 for n=32,64,128 and extend to 256 (since the prompt asserts up to 256); verify convergence across seeds; recompute mean±sd of max_frob and the final attractor plateau.
* **Pass criteria:** All runs converge to the stated attractor statistics; max_frob does not systematically decay with n (including n=256); eff_gap drops to ~1e-4 order and τ rises accordingly.
* **Risk if skipped:** The flagship “scale-independent emergence” could be an artifact of a limited scale range.

---

26. **Reproduce invariance: budget cap does not change the attractor (EXP-081)**

* **Rationale:** “No effect” is a scientific claim: it says the attractor is not an artifact of runaway resources.
* **Scope:** EXP-081, comparison to EXP-080, CLO-088.
* **Approach:** Rerun EXP-081; compare distributions of max_frob/final_frob/macro_n/eff_gap and time-to-plateau against EXP-080; verify budget stays near cap.
* **Pass criteria:** Capped and uncapped runs are statistically indistinguishable in the reported attractor metrics; budget is capped as intended.
* **Risk if skipped:** The attractor might rely on unlimited budget accumulation, undermining the “self-sustaining” interpretation.

---

27. **Reproduce multi-state emergence + k-dependence (EXP-082, EXP-084, EXP-085)**

* **Rationale:** Claim (1) includes frob targets for k=4 and k=8 and asserts macro_n behavior (3 for k=4, 4–5 for k=8) with scale-independence and diminishing returns.
* **Scope:** EXP-082 (k=4 uncapped), EXP-085 (k=4 capped recommended), EXP-084 (k=8), closures CLO-089–092.
* **Approach:** Rerun these sweeps; compute max_frob statistics per scale; measure macro_n distribution; verify budget behavior with cap vs no cap.
* **Pass criteria:** k=4 and k=8 produce the reported stronger frob plateaus; macro_n distributions match (“quadrants empty” phenomenon); scale-independence holds.
* **Risk if skipped:** Reported “richer macro structure” might be overfitting or dependent on uncapped budget.

---

28. **Reproduce near-Markov claims on evolved kernels (EXP-083 and EXP-086)**

* **Rationale:** The project asserts Phase 2 resolves the Phase 1 “macro memory” blocker by creating near-lumpable structure.
* **Scope:** EXP-083 (k=2) + EXP-086 (k=4) non-Markov tests; CLO-090 and CLO-093.
* **Approach:** Rerun; validate nm_mean/nm_max distributions and n_pairs coverage; compare against EXP-074 baseline.
* **Pass criteria:** NM is consistently below stated thresholds at all scales; estimator coverage (n_pairs) is adequate and not hiding rare transitions.
* **Risk if skipped:** “Macro processes remain Markov” could be a measurement artifact.

---

29. **Reproduce cross-layer coupling results (EXP-087) + n=256 spot check**

* **Rationale:** The project claims coupling constrains feasibility (acceptance drops) but does not increase frob; also claims scale-independence persists at n=256 for coupling.
* **Scope:** EXP-087 sweep logs and CLO-094.
* **Approach:** Rerun EXP-087 at n=32/64/128; add explicit n=256 sweep/spot check; compare against uncoupled baseline (EXP-085) using matched seeds.
* **Pass criteria:** Acceptance/feasibility changes with coupling; frob is not systematically improved; n=256 spot check supports the closure’s statement.
* **Risk if skipped:** Coupling “no effect” could hide a bug or a missing n=256 confirmation.

---

30. **Reproduce coupling-strength sweep (EXP-092)**

* **Rationale:** “Coupling strength has no effect across {0,1,2,5,10,20}” is a parametric null claim and must be verified alongside evidence coupling actually changes dynamics.
* **Scope:** EXP-092 outputs and CLO-100.
* **Approach:** Rerun; compute max_frob statistics per strength/scale; verify accept_rate changes monotonically with strength as claimed.
* **Pass criteria:** Macro structure metrics remain within stated variability across strengths; accept_rate decreases with strength (showing coupling is active).
* **Risk if skipped:** Null result might simply reflect an inert coupling pathway.

---

31. **Reproduce two-level ladder propagation (EXP-088)**

* **Rationale:** Recursive coarse-graining is the core “emergence ladder” claim; EXP-088 is the first propagation check.
* **Scope:** EXP-088 outputs and CLO-095.
* **Approach:** Rerun; verify L0 macro kernel frob and L2 frob are non-trivial in all runs; confirm reported variance sources (macro gap, macro_n).
* **Pass criteria:** Non-rank-1 structure persists through the second coarse-graining step in essentially all runs, matching closure statistics.
* **Risk if skipped:** The ladder might only work at L0 and fail under recursion.

---

32. **Reproduce three-level ladder (EXP-090) + outlier verification**

* **Rationale:** Claim (2) is explicit: 29/30 runs have L2 frob>0.1; also claims scale-independence and a specific outlier explanation.
* **Scope:** EXP-090 outputs and CLO-097–098.
* **Approach:** Rerun the full 30-run sweep; reproduce the outlier (seed/scale) and confirm it persists; recompute the “block vs non-block” split and correlation between L0 macro gap and L2 frob.
* **Pass criteria:** 29/30 threshold reproduced; outlier is the same run (or accounted for); correlation and regime split match closure claims within tolerance.
* **Risk if skipped:** The central “three-level ladder” claim could be cherry-picked or non-robust.

---

33. **Reproduce near-Markov across ladder levels (EXP-091)**

* **Rationale:** Claim (3) states near-Markov holds at multiple ladder levels (L0 and L1), with L1 even cleaner.
* **Scope:** EXP-091 outputs and CLO-099.
* **Approach:** Rerun; validate both NM calculations (micro→L0 and L0-macro→L1); check estimator coverage and worst-case seeds.
* **Pass criteria:** NM magnitudes at both levels align with closure; L1 NM is consistently smaller than L0.
* **Risk if skipped:** Ladder may preserve frob but not the Markov property, undermining the “macro processes remain Markov” thesis.

---

34. **Reproduce bimodal attractor characterization via partition entropy (EXP-093)**

* **Rationale:** Claim (10) and CLO-101 interpret emergence as bimodal in occupancy (entropy) while frob remains high in both modes.
* **Scope:** EXP-093 outputs and CLO-101; entropy computations in `runner`.
* **Approach:** Rerun; compute distribution of `h_l0` (and related fractions); verify ~50/50 split and the relationship between entropy mode and information-preservation fractions.
* **Pass criteria:** Clear bimodality (or documented evolution with scale); frob remains high in both regimes; reported counts per regime match.
* **Risk if skipped:** “Bimodal attractor” might be a visualization artifact or depend on a single scale.

---

35. **Reproduce Phase 1 property revisit on Phase 2 macros (EXP-094) with *validated* metrics**

* **Rationale:** EXP-094 is where several positive and negative emergent properties are asserted simultaneously; it must be audited only after σ/MI/eigen/locality/RM are confirmed correct.
* **Scope:** EXP-094 outputs and CLO-102; metric codepaths in `substrate.rs`, `spectral.rs`, `helpers.rs`, and `runner`.
* **Approach:** Rerun EXP-094; recompute each property with an independent reference implementation for small macro kernels; verify regime claims (block vs non-block) and monotonicities.
* **Pass criteria:**

  * **MI:** block-mode seeds show MI ≈ 0.63–0.69 nats; non-block seeds show MI≈0 for genuine reasons (e.g., rank-1 or occupancy collapse).
  * **Eigenvalues:** each seed shows 2–3 non-trivial eigenvalues by a reference solver; block mode has λ₂≈1.
  * **RM:** L0<L1<L2 trend holds as claimed.
  * **σ:** near-zero across levels remains near-zero under the correct entropy-production formula.
  * **Locality:** near-zero values are reproduced and not a degeneracy artifact.
  * **DPI:** “vacuous” claim follows from σ results.
* **Risk if skipped:** The project’s most condensed “properties summary” (and its negative claims) could be driven by a single subtle metric bug.

---

36. **Narrative audit: ensure every quantitative notebook claim is backed by a ledger entry and a reproducible log**

* **Rationale:** Scientific validity requires traceability: every number in the master narrative should map to raw logs generated by the code in the repo snapshot.
* **Scope:** `lab/reengineering_notebook.md` plus `lab/ledger/*.jsonl` and `lab/sweeps/*`.
* **Approach:** Extract all quantitative assertions (thresholds, means, variances, counts, correlations) and link each to a specific EXP and a parser-derived statistic from the raw logs.
* **Pass criteria:** Every claim in the notebook is either (a) directly reproduced from logs, (b) explicitly labeled as conjecture, or (c) removed/updated if unsupported.
* **Risk if skipped:** The repo may “feel” coherent while containing unverified or outdated quantitative statements.
