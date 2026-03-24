# Ticket P6.3 Confirmatory Freeze

## Target check
- A14_only remains right confirmatory target: yes
- comparator set frozen: A14_only, baseline, full_action, full_all, A13_A14, A14_A19

## Metric freeze
- primary: delta_vs_baseline_frob_from_rank1 on n=64,128
- secondary: seed coverage + anchor k_rung=4 comparability

## Budget freeze
- primary scales: n=64,128
- n=256: optional extension, not required for trigger closure
- minimum seeds: 10 per (config,n) at primary scales

## Decision hardening
- theorem upgrade, hybrid-only retention, and A14-only falsification conditions are explicitly machine-readable in decision_logic.yaml
- no run executed in this ticket
