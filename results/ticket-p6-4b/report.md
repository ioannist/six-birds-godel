# Ticket P6.4b audit correction

The 2026-10-03 mathematics review supersedes the earlier `hybrid_ready` verdict. The corrected verdict is `not_ready` under the unchanged P6.3 criteria.

All 120 primary seed metrics are present, but 18 seeds across six comparator cells lack a measured k=4 anchor. Pair-level anchor presence did not meet the frozen per-seed comparability requirement. A14_only also misses the theorem signal threshold at n=64 (0.08382633 < 0.15), and no-new-robustness-failures is not established.

The local gains against the nearest nonempty strict subprogram remain valid. They do not establish a gain over the best measured strict subprogram under the absolute-baseline-shift metric.

This correction reuses existing logs and measurements. No new experiment or independent confirmatory sample was produced. The original resume job manifest records historical execution; the current missing-seed list is in `results/ticket-p6-4a/jobs_resume_exp112.json`.
