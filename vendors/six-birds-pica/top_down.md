AGENT 1

## Section A — Diagnosis: why current coupling is mostly constraining

In the current code, “top‑down coupling” only enters as an **extra positive cost term inside `p2_step`** (edge-mask toggles), namely `penalty = coupling_strength * level1_frob * cross_edge_frac`, which means (i) it can only **veto** certain P2 moves by making them unaffordable under the budget rule, (ii) it does **not** bias P1 rewrites, the protocol/mixture schedule (P3), or P6 budget injection, and (iii) because the factor is proportional to `level1_frob`, the coupling is **weakest exactly when you most need it** (when L1 is near rank‑1, `level1_frob ≈ 0`, the penalty disappears), so it tends to stabilize whatever partition already exists rather than create an amplifying feedback loop that “pushes” the system toward richer macro structure.

Concretely: today the macro signal can only *remove options* (a constraint), not *create selective pressure* (an amplifier).

---

## Section B — Mechanism 1: **Audit‑rebated budget (“P6 income”)**

### Intuition (1 paragraph)

Make P6 stop being diagnostic-only by turning the macro audit into an **internal currency** that refuels the system’s ability to perform P1/P2/P4/P5 moves. If macro structure is nontrivial (e.g., non‑rank‑1 and/or nonzero asymmetry), the system “earns” budget; if it collapses, it stops earning and exploration slows. This is protocol‑clean because it uses only P6 observables computed from the kernel/lens, and it produces *positive feedback* (macro structure → more micro freedom → easier to maintain/create macro structure).

### Exact update rule (pseudocode)

Let `frob1` be L1 Frobenius distance from rank‑1 (already computed as `level1_frob`), and let `sigma1` be an L1 asymmetry (add it to the audit; you already compute a horizon‑T KL in `observe_kernel_metrics`).

Define normalized signals:

```text
f = clamp(frob1 / frob_scale, 0, 1)
s = clamp(sigma1 / sigma_scale, 0, 1)
income = p6_budget_rate * (income_base + income_gain * f * s)
budget <- min(budget_cap, budget + income)
```

Optional “anti-collapse” variant (if you want the strongest push when L1 collapses):

```text
anti = 1 - clamp(frob1 / frob_scale, 0, 1)
income = p6_budget_rate * (income_base + income_gain * anti)
```

### Mapping to P1–P6

* **P6 (audit/accounting):** produces `(sigma1, frob1)` and defines the budget ledger update.
* **P1/P2/P4/P5:** spend budget as already implemented via `drive::accept_or_reject`.
* **P3:** unchanged (still available as an orthogonal lever).

### Why this is not smuggling

No external potential, geometry, or semantic “goal” is introduced. The only “control signal” is an **audit computed from the kernel and lens** already inside the protocol. The budget is already a first-class primitive in your code; this only makes the budget **endogenous** to P6 instead of a constant faucet.

### Concrete insertion points

* `crates/dynamics/src/observe.rs`

  * Extend `level1_audit(...)` to also return `sigma1` (right now it computes metrics but only returns `(group, frob)`).
* `crates/dynamics/src/state.rs`

  * Add `pub level1_sigma: f64` to `State`.
  * Add config knobs to `DynamicsConfig`:

    * `p6_income_base: f64` (default 1.0)
    * `p6_income_gain: f64` (default 0.0 = off)
    * `p6_sigma_scale: f64`, `p6_frob_scale: f64` (scales)
* `crates/dynamics/src/mixture.rs`

  * In `dynamics_step`, after `level1_audit`, store `state.level1_sigma`.
  * In `p6_step`, replace constant boost with the audit-scaled `income` rule (or pass a multiplier into `drive::p6_boost`).

### Minimal experiment (1 EXP)

**Goal:** show sustained nontrivial macro (non‑rank‑1) and/or nonzero asymmetry increases when “income” is turned on.

* **Knobs**

  * `p6_income_gain ∈ {0.0, 1.0, 3.0}`
  * `p6_sigma_scale` set from a quick baseline run median `sigma1` (or use a conservative constant like `1e-3` then tune)
  * `p6_frob_scale` similarly (e.g., `1e-2`)
* **Metrics**

  * time‑series: `level1_frob`, `level1_sigma`, `budget`, accepted move counts (P1/P2/P4/P5)
  * derived: fraction of steps where `level1_frob > ε_frob` and `level1_sigma > ε_sigma`
* **Expected effect size**

  * With income gain on, budget should correlate positively with macro nontriviality; “nontrivial fraction” should increase noticeably vs gain=0.
* **Null control**

  * Replace `(frob1, sigma1)` in income with a shuffled / time‑permuted version; if effect persists, it’s just “more budget,” not top‑down.
* **Failure criterion**

  * Budget saturates immediately (signal too large) or never grows (signal too small), OR viability rejects almost everything. Adjust scales/clamps.

### Main risk/failure mode

If the income function is too steep, you get runaway budget saturation and the system becomes “hyper‑plastic” (structure washes out). If too weak, nothing changes. This is why the clamped normalization (`scale`) matters.

---

## Section C — Mechanism 2: **Audit‑modulated protocol scheduling (“P6→P3 mixer”)**

### Intuition (1 paragraph)

Right now the protocol cycle (P3) is mostly time/phase-based (`protocol_cycle(...)`), not *state*-based. A clean amplifier is: **use macro audit to decide what the protocol does next**. When L1 gets boring (near rank‑1, low asymmetry), shift the mixture toward “structure‑creating” moves (P2/P4/P1). When it becomes too fragmented or unstable, shift toward consolidation (P5) or more trajectory steps. This is top‑down influence via **which primitive gets to act**.

### Exact update rule (pseudocode)

Let `w = protocol_cycle(config.mixt_weights, state.phase, config.bias_strength)`.

Let `f = clamp(level1_frob / frob_scale, 0, 1)` and `s = clamp(level1_sigma / sigma_scale, 0, 1)`.

Define a “boringness” score (many choices; keep it simple):

```text
boring = 1 - (f*s)   # boring≈1 when either frob or sigma is small
```

Then reweight actions:

```text
w[P2Gate]      *= 1 + k_gate      * boring
w[P4Sectors]   *= 1 + k_sectors   * boring
w[P1Rewrite]   *= 1 + k_rewrite   * boring
w[P5Package]   *= 1 + k_package   * (1 - boring)  # optional: consolidate when interesting
w[Trajectory]  *= 1 + k_traj      * (1 - boring)  # optional
w[P6BudgetBoost]*= 1              # keep as-is or also couple
w <- normalize(w)
```

### Mapping to P1–P6

* **P6:** provides `(sigma1, frob1)` driving the mixer.
* **P3:** uses that drive to choose which primitive fires next (autonomous protocol modulation).
* **P1/P2/P4/P5:** unchanged internal meaning; only frequency changes.

### Why this is not smuggling

You’re not injecting any external semantics—only changing **the internal scheduling** of already-allowed primitives using already-available audit signals. This is exactly “P3 as active protocol.”

### Concrete insertion points

* `crates/dynamics/src/mixture.rs`

  * In `dynamics_step`, after getting `weights = protocol_cycle(...)`, apply the reweighting before `pick_action`.
* `crates/dynamics/src/state.rs`

  * Add config knobs:

    * `audit_mix_frob_scale`, `audit_mix_sigma_scale`
    * `audit_mix_k_gate`, `audit_mix_k_sectors`, `audit_mix_k_rewrite`, `audit_mix_k_package`, `audit_mix_k_traj`

### Minimal experiment (1 EXP)

* **Knobs**

  * Enable only one modulation first: `k_gate > 0`, others 0.
  * Then add `k_sectors`.
* **Metrics**

  * action histogram over time (do you actually shift the protocol?)
  * `level1_frob`, `level1_sigma`, and “time to collapse” if collapse still occurs
* **Expected effect**

  * More time spent in P2/P4/P1 when macro is boring; macro should spend less time pinned at rank‑1.
* **Null control**

  * Replace `boring` with same-mean random noise.
* **Failure criterion**

  * No change in action histogram or macro metrics vs baseline.

### Main risk/failure mode

If modulation pushes too hard into P2 gating, you may fragment connectivity and then P5/viability will reject, resulting in stagnation. This is tunable by keeping modulation modest and relying on viability to fence the space.

---

## Section D — Mechanism 3: **Macro affinity “credit assignment” down to micro edges**

### Intuition (1 paragraph)

Your current coupling is scalar and mostly “don’t cut across groups.” A true amplifier needs *credit assignment*: **which micro edges matter** for the macro behavior you measured. A protocol-clean way is to compute a **macro affinity field** (edge-level directional “pressure”) from the L1 macro kernel, then map that field back down to micro edges via the lens partition. Use it to bias P2 gating and/or P1 rewrites so that the micro layer preferentially reinforces edges that support the macro directional structure. This is a clean “top‑down influence” path: emergent macro currents reshape micro feasibility.

### Exact update rule (math/pseudocode)

Given:

* lens partition `g : {0..n-1} → {0..m-1}` (you already have this as `level1_group`)
* macro kernel `M` (you already compute in `build_macro_kernel_exact`)
* stationary distribution `π` of `M`

Define macro edge affinity (with ε for support safety):

```text
A_ab = log( (π_a * M_ab + ε) / (π_b * M_ba + ε) )
C_ab = tanh(A_ab / a0)   # C_ab in [-1, 1]
```

Now for a proposed micro edge toggle `(i -> j)` with `a=g(i)`, `b=g(j)`:

**P2 gating cost shaping**

```text
credit = C_ab
if toggling ON (false -> true):
    cost += base_cost - eta_on * max(0, credit)
if toggling OFF (true -> false):
    cost += base_cost + eta_off * max(0, credit)
```

Optional directional symmetry: apply similar for negative credit to encourage reverse.

**P1 rewrite targeting (optional)**
When choosing `(row=i, col=j)` to perturb:

```text
P(j | i) ∝ exp(beta * C_{g(i), g(j)})   over currently-allowed j (mask true)
```

### Mapping to P1–P6

* **P4:** supplies `g` (sectors / partition of micro states).
* **P6:** supplies affinity/drive extracted from the macro kernel (directionality as accounting).
* **P2:** uses the resulting credit field to shape feasibility/cost of edge deletions/additions.
* **P1:** optionally uses it to bias rewrites toward macro-relevant edges.
* **P3:** still provides route/cycle scheduling; this mechanism gives it something to “work with.”

### Why this is not smuggling

The affinity field is computed entirely from `(M, π)` which are *themselves computed from the kernel and lens*. You are not importing an external target; you’re feeding back **measured macro structure** into micro feasibility, which is exactly the “top‑down = constraint/enablement” reading.

### Concrete insertion points

* `crates/dynamics/src/observe.rs`

  * Add a helper like `macro_affinity_matrix(&macro_k) -> Vec<Vec<f64>>` using `stationary_distribution` + the formula above.
  * Extend `level1_audit(...)` to also return `macro_affinity` (or store it in `State`).
* `crates/dynamics/src/state.rs`

  * Add `pub level1_affinity: Vec<Vec<f64>>` (size `m×m`, small) OR a derived micro-edge field if you want persistence.
  * Add knobs: `affinity_eps`, `affinity_a0`, `affinity_eta_on`, `affinity_eta_off`, `affinity_beta`.
* `crates/dynamics/src/mixture.rs`

  * In `p2_step`, incorporate the directional credit into `penalty` (instead of only the cross-edge scalar).
  * In `p1_step` (optional), replace uniform `col` sampling with affinity-biased sampling.

### Minimal experiment (1 EXP)

* **Knobs**

  * Turn off existing scalar coupling (`coupling_strength=0`) to isolate effect.
  * Enable only `eta_off` first (preserve macro-favored edges), then add `eta_on`.
* **Metrics**

  * `level1_sigma` should increase and remain > 0 for longer
  * distribution of macro affinities `A_ab` (nonzero cycle structure)
  * compare “directed edge asymmetry” at micro: `||K - K^T||_F` (optional diagnostic)
* **Expected effect size**

  * At the same budget, you should see higher sustained `sigma1` and fewer collapses to “almost reversible / almost rank‑1” macro kernels.
* **Null control**

  * Permute macro labels (shuffle rows/cols of `C`) before projecting to micro; effect should largely disappear.
* **Failure criterion**

  * System drives itself into near-absorbing directed cycles (viability may catch); or you get +∞ issues if ε too small and supports become one-way.

### Main risk/failure mode

If you allow affinity to push too hard, you can create one-way support (violating REV-support-like assumptions), causing asymmetry blowups (+∞) and brittle behavior. Use `ε`, `tanh`, and viability constraints to keep it bounded.

---

## Section E — Ranking table

| Mechanism                                                      |                                 Protocol safety |             Implementation difficulty | Expected upside |
| -------------------------------------------------------------- | ----------------------------------------------: | ------------------------------------: | --------------: |
| 1) Audit‑rebated budget (P6 income)                            |                 **Very high** (pure accounting) |        **Low** (few fields + p6_step) | **Medium–High** |
| 2) Audit‑modulated protocol scheduling (P6→P3 mixer)           |                        **High** (schedule only) |   **Low–Medium** (weights modulation) |      **Medium** |
| 3) Macro affinity credit assignment (downward causation field) | **High** (audit-derived, but stronger feedback) | **Medium–High** (new matrix + biases) |        **High** |

---

## Section F — Recommended first implementation ticket (smallest high‑value step)

**Ticket: “Make P6 budget boost endogenous to L1 audit (sigma/frob income)”**

1. **Add audit outputs**

* Edit `crates/dynamics/src/observe.rs`:

  * Change `level1_audit(...) -> (Vec<usize>, f64)` to return `(Vec<usize>, f64, f64)` where the third is `sigma1`.
  * You already compute `metrics = observe_kernel_metrics(&macro_k)`; return `metrics.sigma` (or `metrics.path_asym` if that’s what you want).

2. **Store sigma in State**

* Edit `crates/dynamics/src/state.rs`:

  * Add `pub level1_sigma: f64` to `State` (init to 0.0 in `State::new`).

3. **Compute and apply P6 income**

* Edit `crates/dynamics/src/mixture.rs`:

  * In `dynamics_step`, after `level1_audit`, assign `state.level1_sigma = sigma1`.
  * In `p6_step`, replace `drive::p6_boost(&mut state.budget, ...)` with:

    * `income = config.p6_budget_rate * (config.p6_income_base + config.p6_income_gain * clamp(state.level1_sigma/config.p6_sigma_scale,0,1) * clamp(state.level1_frob/config.p6_frob_scale,0,1))`
    * `state.budget = min(config.p6_budget_cap, state.budget + income)`

4. **Add config knobs (default off)**

* Edit `DynamicsConfig` in `state.rs`:

  * `p6_income_base: f64 = 1.0`
  * `p6_income_gain: f64 = 0.0`  *(so existing behavior stays the same unless enabled)*
  * `p6_sigma_scale: f64 = 1e-3`, `p6_frob_scale: f64 = 1e-2` *(tunable)*

5. **One experiment**

* Run two configs with same seed/kernel:

  * Control: `p6_income_gain=0.0`
  * Treatment: `p6_income_gain=2.0`
* Compare time‑series of `(budget, level1_sigma, level1_frob)` and acceptance counts.

This is the smallest change that turns P6 into an actual driver (amplifier path) while remaining strictly protocol‑clean.


---

AGENT 2

## Section A — Diagnosis of why current coupling is mostly constraining

Right now the “top‑down” channel enters **only** as an **extra cost term on P2 acceptance**:

[
\text{cost} ;=; \mathrm{KL}(K' ,|, K);+; \underbrace{\texttt{coupling_strength}\cdot \texttt{level1_frob}\cdot \texttt{cross_frac}}_{\text{penalty}}
]

where `cross_frac` counts **any flipped edge** whose endpoints lie in different `level1_group`s, regardless of direction.

That makes it a stabilizer / veto, not an amplifier, for three concrete reasons:

1. **Purely negative feedback.**
   The coupling only ever *increases* cost → reduces acceptance → slows change. It cannot increase the probability of any macro‑aligned move; it only blocks moves.

2. **Sign-blindness (penalizes “good” and “bad” equally).**
   In your current `p2_step`, a flip that **reinforces** the Level‑1 boundary (e.g., turning *off* a cross‑group edge) is penalized exactly like a flip that **breaks** it (turning *on* a cross‑group edge).
   So the coupling doesn’t implement “top‑down coherence”; it implements “don’t touch boundary edges.”

3. **Penalty scales up precisely when structure exists.**
   Because the penalty scales with `level1_frob`, it is small when the macro layer is near rank‑1 (no leverage), and large once a non‑rank‑1 macro structure appears—so the moment the system gets “interesting”, coupling tends to **freeze** the micro rewrites instead of **feeding** them.

Net result: your coupling behaves like a **constraint lock** (“protect what exists”) rather than an **amplifier** (“use what exists to drive more structure / new regimes”).

What you want, while staying protocol‑clean, is a *signed* and/or *resource-routing* feedback: upper‑layer audits should change **which** micro rewrites are likely and/or **how** budget gets routed—without injecting any external semantics or potentials.

---

## Section B — Mechanism 1: Signed Boundary Repair Coupling (SBRC)

### Mechanism name

**SBRC — Signed Boundary Repair Coupling**

### One-paragraph intuition

Keep the existing Level‑1 audit (`level1_group`), but change coupling from “penalize boundary touching” to “penalize boundary violation, encourage boundary repair.” In other words: once the macro layer induces a partition, the micro layer should preferentially perform **repairs** that make the micro kernel more consistent with that partition, while still allowing exploration and still respecting viability (connectedness + entropy). This creates an honest **positive feedback loop** (macro → micro repair → stronger macro), not just a brake.

### Exact update rule (pseudocode)

Define for any proposed flip ((i,j)) with old gate (g_{ij} \in {0,1}) (1=on,0=off), new gate (g'*{ij}=1-g*{ij}), and group labels (G(i)\in{0,1}):

Let `same = (G(i)==G(j))`.

Classify the flip:

* **repair** iff
  `(same && old==false && new==true)`  (turn ON within-group)
  OR `( !same && old==true && new==false)` (turn OFF cross-group)
* **violation** iff
  `(same && old==true && new==false)`  (turn OFF within-group)
  OR `(!same && old==false && new==true)` (turn ON cross-group)

Compute:

```text
repair_frac    = n_repair / n_flips_effective
violation_frac = n_violation / n_flips_effective
```

Then replace the current penalty term with a **signed** one:

**Cost for P2 accept/reject**
[
\text{cost} = \mathrm{KL}(K' ,|, K) ;+; \kappa \cdot \texttt{level1_frob} \cdot \text{violation_frac}
]
(i.e., only violations are penalized; repairs are not penalized.)

**Optional proposal bias (stronger “amplifier” version):**
When selecting random ((i,j)) candidates inside `p2_step`, with probability `repair_bias` resample until you hit a *repair-eligible* edge (bounded retries), else sample uniformly.

```rust
if coupling_enabled && l1_group.is_some() && rng.gen::<f64>() < repair_bias {
    for _ in 0..max_resample {
        (i,j) = uniform_pair();
        if is_repair_candidate(i,j,gate_mask,l1_group) { break; }
    }
} else {
    (i,j) = uniform_pair();
}
```

This keeps everything local, stochastic, and falsifiable.

### Mapping to P1..P6 (explicit)

* **P5 (packaging / lens):** `observe::level1_audit` produces `level1_group` from kernel-only spectral/lens operations.
* **P2 (constraints):** the gate mask update is still the only operation; we just bias which constraint flips are proposed and which are costly.
* **P6 (accounting):** budget is still the ledger; the coupling appears only as a budget penalty term derived from audits.
* **P3 (protocol):** optionally activate `repair_bias` only in a protocol phase (e.g., the “consolidate” quarter), leaving exploration phases unbiased.

### Why this is not smuggling

* No external labels, potentials, geometry, or “goal variable.”
* The only signal used is `level1_group` and `level1_frob`, both derived from kernel/lens computations already in-protocol.
* “Repair vs violation” is defined **purely structurally**: it is a relation between a proposed gate flip and an induced partition.

### Concrete insertion points in `six-birds-ladder`

* `crates/dynamics/src/mixture.rs`

  * In `p2_step`:

    * compute `n_repair`, `n_violation` while building `flipped` (you already have `(i,j)` list and can access `state.gate_mask` old/new if you track old state before flip).
    * replace `coupling_penalty` with the signed version.
    * optional: add repair-biased sampling in the flip-selection loop.
* `crates/dynamics/src/state.rs`

  * Add config knobs (minimal set):

    * `coupling_repair_bias: f64` (default 0.0)
    * `coupling_max_resample: usize` (default ~10)

### Minimal experiment to test it (1 EXP)

**EXP:** Fork `EXP-087` (cross-layer coupling) into “087-SBRC”.

* **Config knobs**

  * `coupling_enabled=true`
  * `coupling_strength=5.0` (same)
  * `coupling_repair_bias ∈ {0.0, 0.5, 0.8}`
  * Keep `spectral_guided=true`, `n_clusters=4` (as in EXP-087)

* **Metrics**

  * existing: `snap.level1_frob`, `snap.frob_from_rank1`, `snap.macro_gap`, `snap.sigma`, `p2_accept_rate`
  * add (optional but cheap): `repair_frac` / `violation_frac` aggregated per snapshot (can store counters in `AugmentedState`)

* **Expected effect size**

  * With `repair_bias=0.8`: noticeable increase in **max** and **sustained** `level1_frob` (e.g., +25–100% depending on scale), and higher P2 acceptance vs current penalty (because repairs aren’t penalized).

* **Null control**

  * `coupling_repair_bias=0.0` and signed penalty on violations only should still improve vs baseline sign-blind penalty;
  * full null: restore old coupling penalty.

* **Failure criterion**

  * If `p2_accepted` drops sharply (e.g., accept rate < 5%) **or** `level1_frob` does not increase at all relative to baseline across ≥10 seeds, SBRC isn’t doing real work.

### Main risk/failure mode

Over‑repair can push toward near‑block structure that **violates connectedness**, causing many viability rejections and freezing. (This is mitigated by viability checks and by keeping `repair_bias < 1`.)

---

## Section C — Mechanism 2: Audit‑to‑Ledger Budget Rebates (ALBR)

### Mechanism name

**ALBR — Audit‑to‑Ledger Budget Rebates**

### One-paragraph intuition

Right now the macro layer can only *veto* micro moves by making them more expensive. But “top‑down influence” becomes much stronger if the macro layer can **route budget**—i.e., micro repairs that increase cross‑layer coherence should become self‑funding (they “earn” budget), while coherence‑breaking moves become self‑defunding. This stays inside P6: it is not adding an external reward; it is converting audit‑measured structure into internal spendable budget under a cap.

Crucially: the rebate is **local** (computed from the flip list + cached audit), not a global engineered objective.

### Exact update rule (math/pseudocode)

Reuse the `repair_frac` and `violation_frac` defined in SBRC (computed purely from `level1_group` and the flip directions).

Define a rebate amount:
[
\Delta B ;=; \rho \cdot \texttt{level1_frob}\cdot(\text{repair_frac}-\text{violation_frac})
]
Then after accepting a P2 move:

```rust
state.budget -= base_cost;
state.budget += rebate_rate * state.level1_frob * (repair_frac - violation_frac);
state.budget = min(state.budget, budget_cap_if_any);
```

Optionally clip the rebate below at 0 (rebate-only, no penalty):

```rust
deltaB = max(0.0, rebate_rate * level1_frob * (repair_frac - violation_frac));
```

### Mapping to P1..P6

* **P5:** supplies `level1_group`, `level1_frob` via `level1_audit`.
* **P2:** gating is still the only structural move; repair/violation is defined relative to P2’s own action.
* **P6:** rebate is literally a ledger update rule; it is “currency conversion” from audit to budget.
* **P3:** can restrict rebates to specific phases to prevent runaway.

### Why this is not smuggling

* The “signal” is entirely internal: `level1_group`/`level1_frob` come from the kernel, and repair/violation comes from the gate flip itself.
* You are not injecting a target shape; you are allowing coherence‑preserving rewrites to “pay less / self-fund,” which is exactly what P6‑style accounting is meant to formalize.

### Concrete insertion points

* `crates/dynamics/src/mixture.rs`

  * In `p2_step`, right after acceptance:

    * apply the rebate update to `state.budget`.
* `crates/dynamics/src/state.rs`

  * Add config knob(s):

    * `coupling_rebate_rate: f64` (default 0.0)
    * maybe `coupling_rebate_clip_nonnegative: bool`

### Minimal experiment to test it (1 EXP)

**EXP:** Fork EXP‑087 into “087‑ALBR”.

* **Config knobs**

  * `coupling_enabled=true`
  * `coupling_strength` keep baseline or even set to 0 (so we isolate rebate effects)
  * `coupling_rebate_rate ∈ {0.0, 0.1, 0.5, 1.0}`
  * keep `budget_cap = budget_init` (important: prevents runaway)

* **Metrics**

  * `level1_frob` trajectory and max
  * `budget` trajectory (should rise to cap more often as coherence increases)
  * accepted modification counts (`p2_accepted`, `p1_accepted`)
  * `frob_from_rank1`, `macro_gap`, `sigma`

* **Expected effect size**

  * If it works, you should see **bursty** episodes: once a good macro partition exists, repairs become cheaper/self-funding, increasing accepted P2 moves and raising `level1_frob` and/or maintaining it longer.

* **Null control**

  * `coupling_rebate_rate=0.0` with all else same.

* **Failure criterion**

  * Either (a) no measurable change in `level1_frob` vs null across seeds, or (b) budget saturates immediately and the kernel collapses into a degenerate regime (accept rate spikes but structure dies / viability rejections dominate).

### Main risk/failure mode

Positive feedback runaway (budget hits cap constantly → too many rewrites → thrashing). This is why you *must* keep a **budget cap** on, and why phase-gating rebates (only in consolidation phase) is a good stabilizer.

---

## Section D — Mechanism 3: Macro Cycle-Affinity Backprojection Pump (MCABP)

### Mechanism name

**MCABP — Macro Cycle‑Affinity Backprojection Pump**

### One-paragraph intuition

To get richer macro behavior than “clusters stabilize,” you want **persistent currents / chirality / non-equilibrium structure** that can survive coarse‑graining. You already have a protocol-clean way to measure directional structure: P6’s cycle affinity / path asymmetry (sigma). So let the macro layer **detect its own strongest directed cycle** (2‑cycle or 3‑cycle) and project that back as a *targeted P1 rewrite* on the micro kernel rows that correspond to those macro transitions. This creates a clean top‑down amplifier: **macro current → micro operator tweak → stronger macro current**, without injecting any external direction (the system picks the cycle itself).

### Exact update rule (math/pseudocode)

At each coupling refresh (same place you already call `observe::level1_audit`), compute and store:

1. A “Level‑0 lens mapping” (c(i)\in{0,\dots,m-1}) (micro → macro cluster) using the same mapping you already use to build the macro kernel (currently internal to `level1_audit`; you’ll expose/store it).
2. The macro kernel (K^{(0\to 1)} \in \mathbb{R}^{m\times m}) you already build inside the audit (from (K^\tau)).
3. The max‑affinity directed cycle (C^*) (length 2 or 3), returning its oriented edges, e.g.:

```text
targets = [(a→b), (b→c), (c→a)]  // oriented to match positive affinity
```

Then modify **P1 step** (single-row rewrite) as:

With probability `p1_cycle_pump_prob`:

* pick an oriented macro edge `(a→b)` uniformly from `targets`
* pick a micro row `i` uniformly among states with `c(i)=a`
* rewrite that row to increase mass into the target macro destination:

[
K'*{i j} \propto K*{i j}\cdot
\begin{cases}
(1+\eta) & \text{if } c(j)=b\
1 & \text{otherwise}
\end{cases}
]
then renormalize row (i).

Otherwise fall back to current random-row P1 perturbation.

Budget cost and viability checks remain unchanged.

### Mapping to P1..P6

* **P5:** provides the lens (micro→macro mapping) and macro kernel construction (already in `observe` logic).
* **P6:** provides the “what to reinforce” signal (cycle affinity / sigma), extracted from the macro kernel itself.
* **P1:** performs the actual operator rewrite (targeted row update).
* **P3:** optionally gates `p1_cycle_pump_prob` to phases.
* **P2:** still shapes feasibility via gating; MCABP mainly adds a top‑down amplifier on P1, which is currently absent.

### Why this is not smuggling

* You are not choosing a cycle externally. The cycle is **selected by the kernel’s own audit** (max affinity).
* The backprojection uses only the lens mapping (c(i)) (packaging) and the macro kernel’s own structure.
* No engineered semantics: “cycle” is a purely graph-theoretic object in the Markov kernel.

### Concrete insertion points

* `crates/dynamics/src/observe.rs`

  * Add a function (or extend `level1_audit`) to return:

    * `lens_mapping: Vec<usize>` (micro→macro cluster index)
    * `macro_kernel: MarkovKernel` (small m×m)
    * `cycle_targets: Vec<(usize,usize)>` (or store best 2-cycle/3-cycle)
* `crates/dynamics/src/state.rs`

  * Add cached fields in `AugmentedState`:

    * `level0_cluster: Option<Vec<usize>>`
    * `macro_cycle_targets: Option<Vec<(usize,usize)>>`
* `crates/dynamics/src/mixture.rs`

  * In coupling refresh block inside `dynamics_step`: populate those fields.
  * In `p1_step`: add the cycle-pump branch before the random perturbation branch.

### Minimal experiment to test it (1 EXP)

**EXP:** Fork EXP‑087 into “087‑MCABP”.

* **Config knobs**

  * `coupling_enabled=true`
  * `p1_cycle_pump_prob ∈ {0.0, 0.2, 0.5}`
  * `p1_cycle_eta ∈ {0.01, 0.05, 0.1}` (keep small to preserve entropy)
  * keep `budget_cap=budget_init`, `spectral_guided=true`, `n_clusters=4 or 8`

* **Metrics**

  * existing: `sigma` (macro path-reversal asymmetry), `frob_from_rank1`, `macro_gap`
  * add (optional): `acc_max` on macro kernel (use `six_primitives_core::primitives::p6_audit_acc_max` on the macro kernel) and log it

* **Expected effect size**

  * If it works: clear increase in `sigma` and/or `acc_max`, plus persistence (staying elevated over many snapshots), without collapsing viability.

* **Null control**

  * `p1_cycle_pump_prob=0.0` (pure random P1).

* **Failure criterion**

  * No statistically meaningful increase in `sigma` across ≥10 seeds, **or** P1 acceptance collapses due to entropy/absorbing violations (too strong eta).

### Main risk/failure mode

Thrashing if the “best cycle” changes too frequently: the pump chases a moving target. Mitigation: only refresh targets every `coupling_interval` (you already do), and keep `eta` small.

---

## Section E — Ranking table

| Mechanism                                            |                                          Protocol safety |                                                      Implementation difficulty |                                                                    Expected upside |
| ---------------------------------------------------- | -------------------------------------------------------: | -----------------------------------------------------------------------------: | ---------------------------------------------------------------------------------: |
| **SBRC (Signed Boundary Repair Coupling)**           |             **High** (purely P2+P6 using existing audit) |                                               **Low** (localized to `p2_step`) |          **Medium–High** (turns coupling from brake into amplifier for clustering) |
| **ALBR (Audit‑to‑Ledger Budget Rebates)**            | Medium–High (still P6, but introduces positive feedback) |                                    Low–Medium (budget update + a couple knobs) |     **High** if tuned (can produce bursts / regimes), but can runaway without caps |
| **MCABP (Macro Cycle‑Affinity Backprojection Pump)** |       High (audit selects target; no external direction) | **Medium–High** (need to expose/store macro kernel + cycle targets; modify P1) | **Very High** (non‑equilibrium/chiral macro behavior, richer than “just clusters”) |

---

## Section F — Recommended first implementation ticket (smallest high-value step)

**Ticket: Implement SBRC (signed coupling) + log repair/violation fractions for P2.**

Why this first:

* It is the smallest change that converts coupling from **sign-blind veto** to **directional coherence feedback**.
* It doesn’t require new heavy computations (no extra matrix powers).
* It directly addresses the core diagnosis: current coupling penalizes the exact moves that could create macro separation.

**Concrete checklist for the implementer**

1. In `mixture.rs::p2_step`, compute `n_repair` / `n_violation` over `flipped` using `state.level1_group` + old/new gate value.
2. Replace coupling penalty with `+ strength * level1_frob * violation_frac`.
3. (Optional but recommended) Add `coupling_repair_bias` resampling for repair candidates.
4. Add a minimal debug metric: print repair/violation fractions in `EXP-087` output (or store counters in `Snapshot`).

If SBRC shows a real increase in sustained `level1_frob` (and doesn’t freeze), then ALBR is the next “amplifier knob,” and MCABP is the next “qualitative behavior jump.”
