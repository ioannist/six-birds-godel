# Comprehensive Pending Work Audit — Six Birds Ladder

**Generated:** 2026-02-23
**Source:** Full audit of experiments.jsonl (56 entries), hypotheses.jsonl (57 entries),
results.jsonl (11 entries), closures.jsonl (51 entries), pica_cell_characterization.md
(3476 lines), reengineering_notebook.md, and all sweep logs.

**Purpose:** Self-contained reference for an agent to verify completeness and execute
all remaining work. Nothing should require human memory to identify — everything is
cross-referenced to specific files and line numbers.

**Step count change (2026-02-24):** `total_steps` reduced from `n * 10,000` to `n * 2,000`
(5x reduction). Convergence analysis of 2,074 existing runs showed the system stabilizes
well before the old endpoint. Estimated wall times throughout this document should be
divided by ~5 (e.g., n=256 from ~3h to ~36min per config, n=128 from ~20min to ~4min).

---

## 1. EXPERIMENTS WITH INCOMPLETE DATA COLLECTION

### 1A. EXP-106 n=256 — 43 missing config-seed pairs

**Source:** `lab/ledger/results.jsonl` RES-200-N256-STATUS
**What happened:** Batch timeout (86400s) killed all n=256 jobs before completion.

Missing configs across ALL 10 seeds (40 runs):
- `A13_A21_A19` (10 seeds)
- `chain_A24` (10 seeds)
- `chain_pkg` (10 seeds)
- `chain_SBRC` (10 seeds)

Seed 8 additionally missing (3 runs):
- `A13_A14_A19`, `A13_A3_A19`, `boost_4.0`

**Critical data point:** A13_A14_A19 at n=256 is the KEY TEST per
`pica_cell_characterization.md` line 3264-3267: "If A13/A19 disrupt A14's partition
competition, we'll see Regime B (~0.55). If A14 dominates, we'll see Regime A (>1.0)."

**How to run:** Individual `cargo run --release -p runner -- --exp EXP-106 --seed S --scale 256`
for each missing (config, seed) pair. These are the slowest configs — expect >24h each.

### 1B. EXP-107v2 n=256 — 50 missing config-seed pairs

**Source:** `experiments.jsonl` line 52 (13 configs × 10 seeds = 130 pairs expected).
Sweep log parse shows only 80/130 pairs present. 50 missing.

**Completely missing (0/10 seeds):**
- `A19_only` — 10 missing
- `P1_row_A13` — 10 missing

**Partially missing:**
- `chain_SBRC` — 9 missing (only seed 2 present)
- `chain_A24` — 8 missing (only seeds 2, 3 present)
- `full_all` — 6 missing (seeds 0, 1, 4, 5, 6, 9 missing)
- `A11_A22` — 6 missing (seeds 0, 1, 4, 5, 6, 9 missing)
- `full_action` — 1 missing (seed 9)

**Complete (10/10 seeds):** baseline, chain, A13_only, A24_only, A25_only, sbrc.

**Note:** `mixer` is NOT in the v2-postfix config list (experiments.jsonl line 52) and
was erroneously listed in a prior version of this audit. The characterization doc
cross-scale table "pend" entries for mixer refer to EXP-107v1 (old binary), not v2.

### 1C. EXP-108 n=256 — 70 missing config-seed pairs

**Source:** Sweep log analysis shows only 3/10 configs done per seed.
Completed: `baseline`, `mixer`, `sbrc` (10 seeds each = 30 done)
Missing 7 configs × 10 seeds = 70 runs:
- `P1P2_rows`, `P1P2P3_rows`, `no_extra_P4`, `fa_no_SBRC`, `fa_no_P6row`,
  `full_action`, `full_all`

**Why it matters:** Answers Q4 (does PICA benefit persist at k=16?) and decomposes
WHY full_action works at n=256. See `pica_cell_characterization.md` line 602-605.

### 1D. EXP-106 n=128 seeds 0-2 — 28 missing config-seed pairs

**Source:** RES-200-N256-STATUS
Pre-fix binary leftovers: seed 0 has 5/13, seed 1 has 3/13, seed 2 has 5/13.
Seeds 3-9 are complete (7 seeds × 13 configs = 91 records).
**Lower priority** — 7 seeds may be sufficient for most analyses.

### 1E. EXP-200 campaign Stages 01/02/04 n=256 — 9 timed-out jobs

**Source:** RES-200-S01, S02, S04
- Stage 01 (EXP-104 configs): 3 n=256 jobs timed out
- Stage 02 (EXP-100 configs): 3 n=256 jobs timed out
- Stage 04 (EXP-105 configs): 3 n=256 jobs timed out

**Lowest priority** — redundant with EXP-107/106 n=256 data.

### 1F. EXP-103 n=128 timeouts — 2 configs

**Source:** `pica_cell_characterization.md` lines 791-792
`all_MaxFrob` and `full_lens` timed out at n=128 in the post-review batch (2h limit).
The 24h-timeout batch was expected to capture these but status unknown.
Also: `full_lens` n=128 listed as "pending" in cross-scale table (line 726).

---

## 2. EXPERIMENTS WITH INCOMPLETE OR NO FORMAL ANALYSIS

### 2A. EXP-100 — PICA single-cell sweep (status: "ready", logs exist but incomplete)

**Source:** `experiments.jsonl` line 42
**Tests:** HYP-130 (each action cell produces distinct diagnostic signatures)
**Design:** 13 cells (baseline + A1-A9, A11-A13) × 10 seeds × 3 scales = 390 runs
**Existing data:** 30 sweep log files exist (`sweep_exp100_s{0-9}_n{32,64,128}.log`).

**Coverage by scale (from log parse):**
- **n=32:** COMPLETE — 13 cells × 10 seeds = 130 runs
- **n=64:** COMPLETE — 13 cells × 10 seeds = 130 runs
- **n=128:** INCOMPLETE — only 5 cells (baseline, A1-A4) × 10 seeds = 50 runs.
  **80 missing pairs** (8 cells × 10 seeds: A5-A9, A11-A13 at n=128).

**Priority action:** Formally analyze existing n=32/n=64 data (260 runs) immediately;
complete n=128 runs for remaining 8 cells.
**Also:** Partially covered by EXP-200 Stage 02, but EXP-100 has different diagnostics
(commutators, full macro entries) not available in the campaign runs.
**No results entry** in results.jsonl despite substantial data.

### 2B. EXP-101 — Multi-level PICA dynamics (status: "ready", logs exist but incomplete)

**Source:** `experiments.jsonl` line 43
**Tests:** HYP-131 (multi-level PICA produces richer structure)
**Design (ledger):** 4 PICA configs × 10 seeds × 3 scales = 120 runs using `LadderConfig`
**Actual configs (from log parse):** 7 configs — baseline, sbrc, mixer, full_action,
combo_rm, combo_structure, full_action_safe. The ledger lists 4 but the runner
implemented 7 (3 extra: combo_rm, combo_structure, full_action_safe).

**Coverage by scale (from log parse):**
- **n=32:** 7 configs × 10 seeds = 70 runs (COMPLETE for actual config set)
- **n=64:** 7 configs × 10 seeds = 70 runs (COMPLETE; also has `_full` variant logs)
- **n=128:** INCOMPLETE — only 3 configs (baseline, mixer, sbrc) × 10 seeds = 30 runs.
  **Missing:** full_action, combo_rm, combo_structure, full_action_safe at n=128 =
  **40 missing pairs** (4 configs × 10 seeds).

**Priority action:** Formally analyze existing n=32/n=64 data (140 runs) immediately;
complete n=128 runs for remaining 4 configs. Update ledger to reflect actual 7-config set.
**No results entry** in results.jsonl despite substantial data.
**ALSO NOTE:** n=256 never attempted for EXP-101.

### 2C. EXP-109 — Lagrange probe baseline survey (status: "planned")

**Source:** `experiments.jsonl` line 55
**Tests:** HYP-202, HYP-203, HYP-204, HYP-205
**Design:** 13 configs × 10 seeds × {n=64, n=128} = 260 runs
**Prerequisite:** Lagrange probes implemented (DONE — commit 81819d0)

### 2D. EXP-110 — Lagrange probe scale dependence (status: "planned")

**Source:** `experiments.jsonl` line 56
**Tests:** HYP-202, HYP-203
**Design:** 3 configs × 10 seeds × {n=32, n=64, n=128, n=256} = 120 runs

### 2E. EXP-F1 — Empty baseline control (reviewer-requested, Priority 1)

**Source:** `pica_cell_characterization.md` lines 3369-3388
**Blocks:** All inertness claims (Caveat #1, line 70-72)
**Design:** 5-tier protocol (T0=none, T1=A10, T2=baseline, T3=baseline+X, T4=X alone)
10 seeds, n=64/128/256. Priority T4 configs: A13, A14, A19.
**NOT in experiments.jsonl** — needs ledger entry.

### 2F. EXP-F2 — Fixed-tau evaluation (reviewer-requested, Priority 2)

**Source:** `pica_cell_characterization.md` lines 3390-3404
**Blocks:** Headline bifurcation/crossover claims (Caveat #2, line 74-77)
**Design:** baseline/full_action/A13_A14_A19 at tau=5, tau=20, adaptive.
n=64/128/256, 10 seeds.
**NOT in experiments.jsonl** — needs ledger entry.

### 2G. EXP-F3 — Intermediate scales (reviewer-requested, Priority 2)

**Source:** `pica_cell_characterization.md` lines 3406-3417
**Blocks:** Crossover characterization (Caveat #3, lines 79-82)
**Design:** n=48, 96, 192, 384 for baseline/full_action/A19_only/A13_A14_A19.
10 seeds each.
**NOT in experiments.jsonl** — needs ledger entry.

### 2H. EXP-F4 — Out-of-sample validation (reviewer-requested, Priority 3)

**Source:** `pica_cell_characterization.md` lines 3419-3426
**Design:** Seeds 10-19 for final "best" configs.
**NOT in experiments.jsonl** — needs ledger entry.

### 2I. EXP-099 at n=64/128

**Source:** `reengineering_notebook.md` line 996
**TODO:** "EXP-099 at n=64, n=128" — confirm mixer topology effects scale beyond n=32.
EXP-099 was only run at n=32 (5 conditions × 10 seeds).

---

## 3. CODE GAPS AND INSTRUMENTATION

### 3A. ~~p6_rate_mult and p6_cap_mult never populated~~ FIXED

**Status:** RESOLVED (2026-02-24). Runner now populates both fields (main.rs:7395).
Wave-1 audits.jsonl has 547/547 non-null p6_rate_mult and p6_cap_mult values.
Old `audits_merged_v7.jsonl` is stale; use `lab/runs/campaign_v3/wave_1/audits.jsonl`.

### 3B. EXP-F5 — Partition candidate score instrumentation (not implemented)

**Source:** `pica_cell_characterization.md` lines 3428-3442
**Issue:** "Partition competition" mechanism (F41, F46) is inferred from outcomes.
Need to instrument `compute_p4_partition()` in `lens_cells.rs` to log per-candidate
RM/frob/gap scores, selection decisions, and hysteresis margins.

### 3C. EXP-F6 — Action count instrumentation (not implemented)

**Source:** `pica_cell_characterization.md` lines 3444-3456
**Issue:** Audit records lack per-primitive action counts. Need `p1_count` through
`p6_count` and `traj_count` fields.

### 3D. EXP-F7 — git_sha in audit records (DONE)

**Source:** `pica_cell_characterization.md` lines 3458-3466
**Priority:** 0 (low effort, high provenance value)
**Status:** IMPLEMENTED in commit 81819d0. `build.rs` embeds `GIT_SHA` at compile time
via `cargo:rustc-env`. Runner emits `git_sha` field in audit records.

### 3E. Ablation experiments mentioned but not designed

**Source:** `pica_cell_characterization.md` lines 1412-1427
Four suggested ablation experiments from external review:
1. full_action minus one cell (24 ablations at n=128, 10 seeds)
2. A16 interaction study (full_action + A16 - {Aj})
3. A18 tau mechanism study (baseline vs baseline+A18 at n=32/64/128)
4. Candidate scoring diagnostics (covered by EXP-F5)

---

## 4. HYPOTHESES REQUIRING RESOLUTION

### 4A. Hypotheses with definitive results but stale status

| HYP | Current Status | Should Be | Evidence |
|-----|---------------|-----------|----------|
| HYP-122 | partial → closed | already closed | Has two entries: partial (line 23) then closed (line 24, CLO-102d). Status progression is complete but "partial" entry is non-final. |
| HYP-134 | testing | supported | "CONFIRMED: A25 is inert at n=64 because DPI always satisfied" |
| HYP-135 (v2) | supported | NO ACTION | Ledger line 35 already has status "supported". Listed here for completeness — no update needed. |
| HYP-133 (v2) | partially_supported | close or upgrade | Revised claim supported by EXP-105v2 |
| HYP-123 | not_supported | falsified/closed | CLO-103 written but status never updated |
| HYP-140 | not_supported | falsified/closed | EXP-107 confirms |
| HYP-141 | not_supported | falsified/closed | EXP-107 confirms |

### 4B. Hypotheses blocked by missing data

| HYP | Status | Blocked By |
|-----|--------|-----------|
| HYP-130 | open | EXP-100 logs exist (30 files) but never formally analyzed — needs audit of existing data |
| HYP-131 | open | EXP-101 logs exist (40+ files, 7 configs at n=32/64) but never formally analyzed — needs audit of existing data |
| HYP-148 | testing | Needs EXP-107v2 n=128/256 reconciliation |
| HYP-150 | testing | Needs EXP-107v2 n=128/256 reconciliation |
| HYP-201 | partially_falsified | Needs EXP-106 n=256 10-seed stats for A13_A14_A19 |
| HYP-202 | proposed | EXP-109 data collected (Wave 1, schema 2). Needs SLEM-corrected rerun for spectral probes. `analysis/test_hypotheses.py` ready. |
| HYP-203 | proposed | EXP-109 data collected (Wave 1, schema 2). Needs SLEM-corrected rerun for spectral probes. `analysis/test_hypotheses.py` ready. |
| HYP-204 | reformulated | Needs SLEM-corrected binary rerun — gap_ratio/t_rel fields not in schema 2 data. |
| HYP-205 | proposed | EXP-109 data collected (Wave 1, schema 2). diff_kl available; test script ready. |

### 4C. Superseded hypotheses that should be closed

| HYP | Status | Why Close |
|-----|--------|-----------|
| HYP-100 | partially_supported | Subsumed by spectral-guided dynamics (EXP-080+) |
| HYP-101 | partially_supported | Non-Markovianity confirmed for high macro_n but no further experiments planned (EXP-074 result) |
| HYP-103 | partially_supported | Superseded by spectral-guided approach |
| HYP-104 | partially_supported | Superseded by spectral-guided approach |
| HYP-114 | partially_supported | No further experiments planned |
| HYP-125 | partially_supported | Topology effects noted but frob claim failed |

---

## 5. CLOSURE TODOS

**Source:** `lab/ledger/closures.jsonl`

| CLO | Amendment | TODO |
|-----|-----------|------|
| CLO-085 v2 | n=256 value untraceable | "run EXP-077/079 at n=256 and commit sweep logs" |
| CLO-085 v3 | n=256 data point retracted | Same TODO as v2 — reinstating requires n=256 runs |
| CLO-087 v2 | Sweep generated with old code | "regenerate sweep_exp080.log with current code" |
| CLO-094 v2 | n=256 spot check unverifiable | "run and commit n=256 sweep, or remove n=256 claim" — **NOTE: superseded by CLO-094 v3** (closures.jsonl line 43) which corrects apples-to-oranges accept rate comparison. The n=256 TODO still stands but the accept rate framing changed. |

---

## 6. LEGACY EXPERIMENT AMENDMENT TODOS

**Source:** `experiments.jsonl` amendment entries

| Exp | Amendment | TODO |
|-----|-----------|------|
| EXP-077 v2 | Extend to n=256 (CLO-085 support) |
| EXP-079 v2 | Extend to n=256 (CLO-085/086 support) |
| EXP-080 v3 | Regenerate sweep + extend to n=256 |
| EXP-085 v2 | Extend to n=256 (CLO-094 support) |
| EXP-087 v2 | Regenerate sweep + extend to n=256 |
| EXP-090 v2 | n=256 spot check not backed by artifact |
| EXP-092 v2 | Regenerate sweep (log format change) |

---

## 7. OPEN QUESTIONS REQUIRING NEW EXPERIMENTS

**Source:** `pica_cell_characterization.md` "Open Questions" sections

| Q | Line | Question | Experiment Needed |
|---|------|----------|-------------------|
| Q3 | 599 | Can A20 be differentiated from A19? | A20 + A22 experiment |
| Q4 | 602 | Does PICA benefit persist at k=16? | EXP-108 full_action configs |
| Q6 | 612 | Minimum cell count for n=128 REV? | Ablation study (line 1412) |
| Q7 | 1595 | Is A13_A18_A19 REV rate truly ~17% at n=128? | 10-seed sweep at n=128 |
| Q8 | 619/1597 | Why does full_action drive weak seeds to REV? / Does A13_A14_A19 outperform chain at n=128? | Mechanistic study / post-fix data |
| Q9 | 623 | What determines macro_gap = 0.393 attractor? | Theoretical / parametric scan |
| Q10 | 627 | Can A13 mechanism be separated from ensemble? | A13-only eff_gap analysis |
| Q11 | 631 | Critical n for REV vanishing? Functional form? | EXP-F3 intermediate scales |
| Q9' | 1672 | Why does A14_only produce high frob when spectral wins 87%? | Instrumented runs (EXP-F5) |
| Q10' | 1675 | MaxFrob + P1-row cells combination? | New combo experiment |
| Q11' | 1789 | Why does full_action preserve sigma_ratio=0.49? | Ablation / mechanistic |
| Q12 | 1792 | Is k=8 peak emergent or artifact of n_clusters? | n_clusters=4,16 test |
| Q13 | 1795 | Can budget cap steer away from REV? | Budget cap sweep |
| Q14 | 1892 | Does A13+A11 combine additively? (top priority) | P1_row_A13 + A11_A21 |
| Q15 | 1894 | Why does A24 antagonize A13? | Mechanistic study |
| KEY | 3264 | A13_A14_A19 Regime A or B at n=256? | EXP-106 completion |

**Note on Q numbering:** The characterization doc introduces questions across multiple
findings with independent Q counters that reset/overlap (Q3-Q11 in the main open questions
section, then Q7-Q8 at line 1595, Q9-Q10 at line 1672, Q11-Q13 at line 1789, Q14-Q15 at
line 1892). The table above lists all unique questions with their source line numbers.
Primed labels (Q9', Q10', Q11') denote later-added questions whose numbers collide with
the earlier section.

---

## 8. UNTESTED COMBINATIONS

**Source:** `pica_cell_characterization.md` various sections

| Combination | Line | Why Important |
|------------|------|--------------|
| A13 + A11 (two independent axes) | 1888 | "top priority for future experiments" |
| A11 + A22 + A13 | 582 | A11+A22 is "alternative axis"; untested with A13 stabilizer |
| A13_A15_A19 | 2891 | Alternative lens in triplet (vs A14) |
| A13_A16_A19 | 2891 | Alternative lens in triplet (vs A14) |
| A13_A17_A19 | 2891 | Alternative lens in triplet (vs A14) |
| A20 + A22 (packaging differentiation) | 599 | Would distinguish A20 from A19 |
| MaxFrob + P1-row cells | 1675 | Merges EXP-102/103 best findings |
| boost_2.0 at n=128 | 1343 | Boost resonance at n=64 untested at n=128 (post-fix batch excluded it) |

---

## 8B. DATA GAP ROWS IN CHARACTERIZATION TABLES

**Source:** `pica_cell_characterization.md` cross-scale tables and finding tables.
Cells marked `—`, `---`, or `pend` represent missing data points. Representative examples:

| Line | Config | Scale | Gap Type | Needed From |
|------|--------|-------|----------|-------------|
| 217 | baseline | n=32 decomposition | `--` placeholder | Already known (filler row) |
| 853 | A13_A14_A19 | n=64 | tau = `—` | EXP-103 or EXP-106 n=64 |
| 3350 | boost_0.1 | n=128, n=256 | frob = `—` | EXP-106 n=128 (backup only has n=256 3 seeds) |
| 3351 | P1_row_A13 | n=256 | frob = `—` | pending EXP-106 n=256 |
| 726 | full_lens | n=128 | frob pending | EXP-103 n=128 (timed out at 2h) |

Many additional `—` cells exist throughout the tables (estimated 40+ unique gaps).
Most are addressed by completing EXP-106 n=256 (Section 1A) and EXP-108 (Section 1C).
The gaps are NOT individually itemized here because they are downstream of the
experiment completions already listed in Sections 1A-1F.

---

## 9. REENGINEERING NOTEBOOK LOOSE ENDS

**Source:** `lab/reengineering_notebook.md`

| Line | Item | Status |
|------|------|--------|
| 196 | TODO: check DPI vs slow-mode compatibility | Unanswered theoretically |
| 201 | TODO: define bridge/memory operator | Deprioritized (Phase 4 shelved) |
| 416 | EXP-090 n=256 spot check — no committed artifact | Unresolved |
| 996 | TODO: EXP-099 at n=64, n=128 | Not run |
| 997 | Paper-ready summary | Not started |
| Phase 3 | Test for oscillation in cross-layer coupling | Never explicitly tested |
| Phase 4 | Implement bridge operators | Shelved, never formally cancelled |

---

## 10. PRIORITY ORDERING

### Tier 1 — Blocks active claims or hypotheses
1. **EXP-106 n=256 completion** (43 runs) — KEY TEST for A13_A14_A19
2. **EXP-107v2 n=256 completion** (50 runs) — fills cross-scale table, blocks HYP-201
3. **EXP-F1 empty baseline** (~120 runs) — blocks ALL inertness claims
4. **Fix p6_rate_mult/p6_cap_mult runner gap** (code change) — easy, high value
5. **Analyze existing EXP-100 data** (0 new runs, 260 records at n=32/64) — unblocks HYP-130
6. **Analyze existing EXP-101 data** (0 new runs, 140 records at n=32/64) — unblocks HYP-131

### Tier 2 — Important for scientific claims
7. **EXP-100 n=128 completion** (80 runs) — 8 missing cells at n=128
8. **EXP-101 n=128 completion** (40 runs) — 4 missing configs at n=128
9. **EXP-108 missing configs** (70 runs) — full_action decomposition at n=256
10. **EXP-F2 fixed-tau** (~90 runs) — blocks bifurcation headline claims
11. **EXP-F3 intermediate scales** (~160 runs) — REV crossover functional form
12. **Reconcile HYP-148/150** with EXP-107v2 data — status update
13. **Close stale hypotheses** (HYP-134, 133, 123, 140, 141) — ledger hygiene

### Tier 3 — New science
14. **EXP-109 Lagrange survey** (260 runs) — HYP-202..205
15. **EXP-110 Lagrange scaling** (120 runs)
16. **Q14: A13+A11 combo** (~40 runs) — "top priority for future experiments"
17. **Q6: REV ablation study** (~240 runs) — minimum REV subset
18. **Alternative lens triplets** (A13_A15_A19, A13_A16_A19, A13_A17_A19)

### Tier 4 — Robustness and infrastructure
19. **EXP-F4 out-of-sample seeds** (~80 runs)
20. **EXP-F5 partition instrumentation** (code + runs)
21. **EXP-F6 action count instrumentation** (code + runs)
22. **EXP-099 at n=64/128** (topology scaling)
23. **EXP-106 n=128 seeds 0-2** (28 runs)

### Tier 5 — Legacy cleanup
24. Legacy amendment TODOs (EXP-077/079/080/085/087/090/092 n=256 / sweep regen)
25. Closure TODOs (CLO-085/087/094)
26. EXP-200 Stage 01/02/04 n=256 (9 runs)
27. Notebook loose ends (bridge operator cancellation, paper draft)

---

## VERIFICATION CHECKLIST FOR AUDITING AGENT

An agent reviewing this document should verify:

- [ ] Every experiment in `experiments.jsonl` with status != "completed" is listed above
- [ ] Every hypothesis in `hypotheses.jsonl` with non-final status (including partially_supported, partial, closed-with-caveats) is listed
- [ ] Table data gaps ("pend" / "---" cells) in `pica_cell_characterization.md` are covered by experiment completions in Sections 1A-1F (Section 8B lists representative examples, not exhaustive enumeration)
- [ ] Every TODO in `experiments.jsonl` amendments is listed in Section 6
- [ ] Every TODO in `closures.jsonl` is listed in Section 5 (including supersession notes)
- [ ] Every EXP-F experiment from `pica_cell_characterization.md` lines 3364-3467 is listed (EXP-F1..F6 in Sections 2/3, EXP-F7 in Section 3D as DONE)
- [ ] Every open question (Q3-Q15 plus duplicates) from `pica_cell_characterization.md` is listed in Section 7
- [ ] Every untested combination from the doc is listed in Section 8
- [ ] The code gap (p6_rate_mult, EXP-F5, EXP-F6) is listed in Section 3
- [ ] `reengineering_notebook.md` TODOs are listed in Section 9
- [ ] Sweep log cross-reference: EXP-100 has 30 logs (needs audit), EXP-101 has 40 logs but no results entry
- [ ] EXP-108 has logs but only 3/10 configs per seed
- [ ] No item from any source file is missing from this audit
