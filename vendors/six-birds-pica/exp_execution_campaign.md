Plan: Experiment Execution Campaign
Context
The PICA characterization campaign (EXP-100..108) has ~233 missing config-seed pairs across 5 experiments, plus 2 new experiments (EXP-109/110) needing runner functions. The pending work audit (lab/pending_work_audit.md) catalogs everything. We need to execute these systematically on a 48-core machine with 44 parallel slots, tracking progress in files and producing reviewer reports between waves.

Key constraint: Each experiment function runs ALL its configs sequentially (10-14 configs per seed). At n=256, one config takes ~2-4h, so running all configs wastes 20+h on already-completed ones. A --config filter flag is essential infrastructure.

Timing estimates (from stage_status.json):

n=64: ~8s per config
n=128: ~20min per config
n=256: ~2-4h per config (slowest configs: chain_SBRC, chain_A24, chain_pkg, A13_A21_A19)
Phase 0: Infrastructure (code changes, no experiments)
0A. Add --config CLI filter to runner
File: crates/runner/src/main.rs

Add to Args struct:


/// Filter to a single config label (skip others)
#[arg(long)]
config: Option<String>,
Pass args.config.as_deref() into each run_exp_*() function. Inside each function, wrap the config iteration loop:


for (label, pat) in &configs {
    if let Some(filter) = config_filter {
        if *label != filter { continue; }
    }
    run_exp_100_single(seed, n, ln_n, pat, label, exp_id);
}
Apply to: run_exp_100, run_exp_101, run_exp_102..108, and any new experiment functions.

Also update run_batch.py to support a config field in job JSON and pass --config to the runner.

0B. Fix p6_rate_mult/p6_cap_mult audit gap
File: crates/runner/src/main.rs (in run_exp_100_single)

After dynamics completes, read pica_state.active_p6_rate_mult and pica_state.active_p6_cap_mult from the trace and write them to the KEY_AUDIT_JSON record. These fields exist in AuditRecord (audit.rs:88-89) but are never populated by the runner.

0C. Add stdout line-flushing
File: crates/runner/src/main.rs

After each println!("KEY_*...") output line, add std::io::Write::flush(&mut std::io::stdout()).ok();. This ensures real-time log visibility when output is redirected to files.

Alternatively (simpler, no code change): use stdbuf -oL prefix in launcher scripts. Prefer the stdbuf approach since it's zero code change and applies universally.

0D. Implement run_exp_109() — Lagrange baseline survey
File: crates/runner/src/main.rs

The Lagrange probes are already computed in multi_scale_scan() (commit 81819d0) for every experiment. EXP-109 just needs a config list that covers the interesting configs:


fn run_exp_109(seed: u64, scale: usize, config_filter: Option<&str>) {
    let n = scale.max(8);
    let ln_n = (n as f64).ln();
    let configs: Vec<(&str, PicaConfig)> = vec![
        ("baseline",        PicaConfig::baseline()),
        ("A13_only",        PicaConfig::baseline().with_cell(2, 5)),
        ("A14_only",        PicaConfig::baseline().with_cell(3, 2)),
        ("A16_only",        PicaConfig::baseline().with_cell(3, 4)),
        ("A17_only",        PicaConfig::baseline().with_cell(3, 5)),
        ("A19_only",        PicaConfig::baseline().with_cell(2, 3)),
        ("A25_only",        PicaConfig::baseline().with_cell(5, 5)),
        ("P1_row_A13",      /* same as EXP-107 */),
        ("A13_A14_A19",     /* same as EXP-106 */),
        ("full_action",     PicaConfig::full_action()),
        ("full_all",        PicaConfig::full_all()),
        ("full_lens",       PicaConfig::full_lens()),
        ("chain_SBRC",      /* same as EXP-107 */),
    ];
    // Same pattern: iterate configs with filter, call run_exp_100_single
}
Add "EXP-109" to the dispatch match in main().

0E. Implement run_exp_110() — Lagrange scale dependence
File: crates/runner/src/main.rs


fn run_exp_110(seed: u64, scale: usize, config_filter: Option<&str>) {
    let configs: Vec<(&str, PicaConfig)> = vec![
        ("baseline",    PicaConfig::baseline()),
        ("full_action", PicaConfig::full_action()),
        ("A14_only",    PicaConfig::baseline().with_cell(3, 2)),
    ];
    // Same pattern
}
0F. Implement run_exp_f1() — Empty baseline
File: crates/runner/src/main.rs

This is the critical inertness control: PicaConfig::none() (all cells disabled).


fn run_exp_f1(seed: u64, scale: usize) {
    let n = scale.max(8);
    let ln_n = (n as f64).ln();
    let pat = PicaConfig::none();
    run_exp_100_single(seed, n, ln_n, &pat, "empty", "EXP-F1");
}
0G. Build release binary

cargo build --release
cargo test --workspace  # verify nothing broken
0H. Create campaign infrastructure
Create lab/runs/campaign_v3/ with:

execution_plan.md — Copy of this plan with live status updates
wave_N/manifest.json — Job list for each wave (consumed by run_batch.py)
wave_N/report.md — Post-completion analysis for reviewer
progress.md — Live dashboard updated after each check-in
Launcher approach: Extend run_batch.py to accept the config field in job JSON. Each wave gets a manifest.json generated by a small Python helper. Launch with:


python analysis/run_batch.py run --jobs lab/runs/campaign_v3/wave_1/manifest.json \
  --parallelism 44 --timeout 172800 --output-dir lab/runs/campaign_v3
For stdbuf, modify run_batch.py's run_one_job to prepend ["stdbuf", "-oL"] to the command.

Wave 1: Fast Completions + Background n=256 Start
When: Immediately after Phase 0 build.
Estimated wall time: ~1.5h for fast jobs; n=256 continues in background for ~4-8h.
Slots: 44 parallel.

Wave 1A: Trivial + Fast jobs (fill slots as n=256 jobs start)
Experiment	Scale	Jobs	Est. Time/Job	Total CPU
EXP-F1	n=32	10 seeds × 1 config	~3s	trivial
EXP-F1	n=64	10 seeds × 1 config	~8s	trivial
EXP-109	n=64	10 seeds × 13 configs = 130	~8s	~17min
EXP-110	n=32	10 seeds × 3 configs = 30	~2s	trivial
EXP-110	n=64	10 seeds × 3 configs = 30	~8s	~4min
Subtotal: 210 jobs, all complete in <5 min.

Wave 1B: Medium jobs (n=128 completions)
Experiment	Scale	Jobs	Est. Time/Job	Total CPU
EXP-100 n=128	128	8 cells × 10 seeds = 80	~20min	27h
EXP-101 n=128	128	4 configs × 10 seeds = 40	~30min	20h
EXP-F1 n=128	128	10 seeds × 1 config	~20min	3.3h
EXP-109 n=128	128	13 configs × 10 seeds = 130	~20min	43h
EXP-110 n=128	128	3 configs × 10 seeds = 30	~20min	10h
Subtotal: 290 jobs × 20-30min = ~103 CPU-hours. With 44 slots: ~2.3h wall.

Wave 1C: Background n=256 (start immediately, run overnight)
Experiment	Scale	Jobs	Est. Time/Job	Total CPU
EXP-106 n=256	256	43 missing pairs	~3h	129h
EXP-107v2 n=256	256	50 missing pairs	~3h	150h
Subtotal: 93 jobs × ~3h = ~279 CPU-hours. With 44 slots: ~6.3h wall.

Wave 1 Total: 593 jobs.
Scheduling logic: Launch all 593 jobs in a single manifest. run_batch.py with 44 workers will process them by finishing fast jobs first (they complete in seconds/minutes), then n=128 jobs (~20min each), then n=256 jobs (~3h each). The ProcessPoolExecutor automatically backfills freed slots.

Manifest structure — each job entry:


{
  "exp": "EXP-107", "seed": 5, "scale": 256, "config": "A19_only",
  "stage": "wave_1"
}
For experiments where ALL configs are missing (like EXP-109, EXP-F1), omit config field to run all configs.

For experiments where specific configs are missing (EXP-106 n=256, EXP-107v2 n=256), include config field.

Wave 1 Report: Generated when n=128 jobs complete (~2.5h)
Report 1 contents (lab/runs/campaign_v3/wave_1/report.md):

EXP-100 n=128 completion: 8 new cells × 10 seeds. Frob/sigma medians vs baseline.
EXP-101 n=128 completion: 4 configs × 10 seeds. Multi-level ladder results.
EXP-F1 empty baseline: n=32/64/128. Confirms/refutes inertness claims.
EXP-109 n=64 Lagrange survey: step_entropy, pla2_gap, geo_R², diff_KL, t_rel, gap_ratio across 13 configs.
n=256 progress check: how many of the 93 background jobs have completed so far?
Updated hypothesis status: HYP-130 (EXP-100), HYP-131 (EXP-101).
Wait for reviewer feedback before proceeding to Wave 2.

Wave 2: Lagrange + n=256 collection (after Report 1 review)
When: After reviewer clears Report 1. n=256 background jobs may still be running.
Estimated wall time: ~1-2h for new jobs; collect any completed n=256 results.

Wave 2A: New medium jobs
Experiment	Scale	Jobs	Est. Time/Job	Total CPU
EXP-110 n=256	256	3 configs × 10 seeds = 30	~3h	90h
EXP-108 n=256	256	70 missing pairs	~3h	210h
Subtotal: 100 jobs. With 44 slots: ~7h wall (runs alongside remaining Wave 1 n=256).

Wave 2B: Collect completed n=256 from Wave 1
By this point (~4-6h after Wave 1 launch), many Wave 1 n=256 jobs should be done. Parse completed logs and generate interim analysis.

Wave 2 Report
Report 2 contents (lab/runs/campaign_v3/wave_2/report.md):

EXP-109 n=128 Lagrange results (from Wave 1 — should be done by now).
EXP-110 n=32/64/128 Lagrange scaling profiles.
First n=256 results: EXP-106 and EXP-107v2 completed pairs.
Hypothesis updates: HYP-202..205 (Lagrange), HYP-201 (n=256 partial).
n=256 completion progress dashboard.
Wait for reviewer feedback before proceeding to Wave 3.

Wave 3: Final n=256 collection + analysis (after Report 2 review)
When: After reviewer clears Report 2. Most/all n=256 jobs should be done.

Wave 3 Activities
Collect ALL remaining n=256 logs (EXP-106, EXP-107v2, EXP-108, EXP-110).
Run collect_audits.py to parse all new logs into audits JSONL.
Run report_stage.py for comprehensive median/IQR analysis.
Fill in cross-scale tables in pica_cell_characterization.md.
Resolve KEY TEST: A13_A14_A19 at n=256 — Regime A or B?
Wave 3 Report
Report 3 contents (lab/runs/campaign_v3/wave_3/report.md):

Complete cross-scale table (n=32 through n=256) for all configs.
EXP-106 n=256: A13_A14_A19 result (Regime A vs B — campaign's most important question).
EXP-107v2 n=256: 50 new data points — partition competition verification.
EXP-108 n=256: full_action decomposition at scale.
EXP-110 n=256: Lagrange probes at scale.
Hypothesis resolutions: HYP-201, HYP-148, HYP-150.
Updated findings: F42 refinement, F46 extension to all lens configs.
Wave 4: Tier 2 + Tier 3 (after Report 3 review)
Analysis tasks (no new runs):

Close stale hypotheses: HYP-134, HYP-133, HYP-123, HYP-140, HYP-141
Reconcile HYP-148/150 with final data
Formal analysis of EXP-100 existing n=32/64 data → HYP-130
Formal analysis of EXP-101 existing n=32/64 data → HYP-131
New experiments (if reviewer approves):

Q14: A13+A11 combo (~40 runs at n=128)
Alternative lens triplets: A13_A15_A19, A13_A16_A19, A13_A17_A19 (~30 runs each)
Monitoring Protocol
Every 30 minutes while experiments run:
Check which background jobs have completed:


# Count completed logs (contain KEY_AUDIT_JSON or KEY_100_MACRO)
for f in lab/runs/campaign_v3/wave_*/*.log; do
  if grep -q "KEY_AUDIT_JSON\|KEY_100_MACRO" "$f" 2>/dev/null; then
    echo "DONE: $(basename $f)"
  elif [ -s "$f" ]; then
    echo "RUNNING: $(basename $f) ($(wc -l < $f) lines)"
  else
    echo "EMPTY: $(basename $f)"
  fi
done
Update progress.md with:

Jobs completed / total per wave
Any failures or empty logs (indicating problems)
Estimated time to wave completion
Spot-check a couple of running logs to verify output is growing:


tail -3 lab/runs/campaign_v3/wave_1/EXP-107_s5_n256_A19_only.log
After a wave's target jobs complete:
Run collect_audits.py on new logs
Run report_stage.py for summary statistics
Write wave_N/report.md with findings
Present report to reviewer and wait
Progress Tracking Files
lab/runs/campaign_v3/progress.md
Updated after each check-in:


# Campaign v3 Progress

## Wave 1 — Status: RUNNING
- Fast (n≤64): 210/210 complete
- Medium (n=128): 180/290 complete
- Background (n=256): 12/93 complete
- Started: 2026-02-23T19:00Z
- Est. completion (n=128): 2026-02-23T21:30Z
- Est. completion (n=256): 2026-02-24T01:00Z

## Wave 2 — Status: PENDING (awaiting Report 1 review)
...
lab/runs/campaign_v3/wave_N/manifest.json
The actual job list consumed by run_batch.py. Generated once per wave.

lab/runs/campaign_v3/wave_N/report.md
Post-completion analysis for reviewer. Includes:

Summary statistics (frob, sigma medians with IQR)
Hypothesis status updates
Any anomalies or unexpected results
Recommendations for next wave
Total Job Count
Wave	n=64	n=128	n=256	Total
Wave 1	210	290	93	593
Wave 2	0	0	100	100
Wave 3	0	0	(collect)	0
Wave 4	TBD	TBD	TBD	TBD
Total	210	290	193	693
Estimated total CPU time: ~560h across all waves.
Estimated wall time: ~12-18h with 44 slots (dominated by n=256 jobs).

Files Modified
Code changes (Phase 0):
crates/runner/src/main.rs — add --config flag, fix p6 audit gap, add EXP-109/110/F1
analysis/run_batch.py — support config field, add stdbuf -oL prefix
New files:
lab/runs/campaign_v3/progress.md
lab/runs/campaign_v3/wave_N/manifest.json (per wave)
lab/runs/campaign_v3/wave_N/report.md (per wave, after completion)
Updated after results:
lab/ledger/results.jsonl — new RES entries
lab/ledger/hypotheses.jsonl — status updates
lab/ledger/closures.jsonl — new closures
lab/pica_cell_characterization.md — fill table gaps, update findings
Verification
After each wave:

cargo test --workspace — no regressions
python analysis/collect_audits.py — all new logs parse cleanly
python analysis/report_stage.py — summary stats match expectations
Spot-check: jq '.multi_scale_scan[0]' < sample_audit.json — Lagrange fields present (EXP-109)
Cross-check progress.md counts against actual log files
What We Are NOT Doing
No EXP-F2/F3 yet — these need new runner function design (fixed-tau, intermediate scales). Defer to Wave 4+.
No EXP-F5/F6 instrumentation — code-heavy, not blocking Tier 1.
No legacy EXP-077..092 reruns — Tier 5, low priority.
No paper draft — deferred until all n=256 data collected.