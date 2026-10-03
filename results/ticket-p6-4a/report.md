# Ticket P6.4a Primary-Coverage Completion Rerun

- exp lineage: EXP-112
- canonical metric: delta_vs_baseline_frob_from_rank1
- primary coverage complete: no
- final readiness verdict: not_ready
- A14_only remains focus: False

Readiness applies the frozen signal, comparator, robustness, and per-seed rung coverage rules.
Rescoring existing logs does not constitute a new experiment or independent confirmation.

Remaining gaps:
- baseline@n=64: remaining_required=1, anchor_missing_count=1
- full_action@n=64: remaining_required=5, anchor_missing_count=5
- full_all@n=64: remaining_required=2, anchor_missing_count=2
- full_all@n=128: remaining_required=2, anchor_missing_count=2
- A14_A19@n=64: remaining_required=6, anchor_missing_count=6
- A14_A19@n=128: remaining_required=2, anchor_missing_count=2
