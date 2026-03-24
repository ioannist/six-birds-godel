# Ticket 06 Robustness and Sensitivity Audit

## Setup
- Models: chains C2..C6 and Boolean lattices B1..B3.
- Families: chain all monotone inflationary, chain closure-only, chain step-family, Boolean all monotone inflationary.
- Benchmarks: uniform, top_heavy, bottom_heavy, middle_heavy.
- Costs: moved_points_cost, total_rank_lift_cost, average_rank_lift_cost, normalized_total_rank_lift_cost.
- Tie modes: keep_all_nondominated, dedup_equal_points.

## Family Metrics
- boolean_all_monotone_inflationary: benchmark_sensitivity=0.2296, cost_sensitivity=0.0601, tie_change_rate=0.6667.
- chain_all_monotone_inflationary: benchmark_sensitivity=0.3659, cost_sensitivity=0.1174, tie_change_rate=0.4625.
- chain_closure_only: benchmark_sensitivity=0.3893, cost_sensitivity=0.1115, tie_change_rate=0.3875.
- chain_step_family: benchmark_sensitivity=0.0000, cost_sensitivity=0.1050, tie_change_rate=0.2000.

## Notes
- All runs were deterministic and exhaustive within each listed family.
- Raw frontier rows and per-operator frequencies are in CSV/JSON outputs.
