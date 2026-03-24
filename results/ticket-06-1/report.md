# Ticket 6.1 Hypothesis Filters and Invariants Sweep

## Variant outcomes
- uniqueness_up_to_score_tie_quotient | all_monotone_inflationary -> fails_with_minimal_failure
- uniqueness_up_to_score_tie_quotient | closure_only -> fails_with_minimal_failure
- uniqueness_up_to_score_tie_quotient | bounded_lift_le_1 -> fails_with_minimal_failure
- uniqueness_up_to_score_tie_quotient | bounded_lift_le_2 -> fails_with_minimal_failure
- uniqueness_up_to_score_tie_quotient | chain_step_family -> fails_with_minimal_failure
- uniqueness_up_to_symmetry | all_monotone_inflationary -> fails_with_minimal_failure
- uniqueness_up_to_symmetry | closure_only -> fails_with_minimal_failure
- uniqueness_up_to_symmetry | bounded_lift_le_1 -> fails_with_minimal_failure
- uniqueness_up_to_symmetry | bounded_lift_le_2 -> fails_with_minimal_failure
- uniqueness_up_to_symmetry | chain_step_family -> inconclusive_not_applicable
- benchmark_stability_fixed_cost_tie | all_monotone_inflationary -> fails_with_minimal_failure
- benchmark_stability_fixed_cost_tie | closure_only -> fails_with_minimal_failure
- benchmark_stability_fixed_cost_tie | bounded_lift_le_1 -> fails_with_minimal_failure
- benchmark_stability_fixed_cost_tie | bounded_lift_le_2 -> fails_with_minimal_failure
- benchmark_stability_fixed_cost_tie | chain_step_family -> survives_on_searched_slice
- cost_stability_fixed_benchmark_tie | all_monotone_inflationary -> fails_with_minimal_failure
- cost_stability_fixed_benchmark_tie | closure_only -> fails_with_minimal_failure
- cost_stability_fixed_benchmark_tie | bounded_lift_le_1 -> survives_on_searched_slice
- cost_stability_fixed_benchmark_tie | bounded_lift_le_2 -> fails_with_minimal_failure
- cost_stability_fixed_benchmark_tie | chain_step_family -> fails_with_minimal_failure
- chain_step_containment | all_monotone_inflationary -> fails_with_minimal_failure
- chain_step_containment | closure_only -> fails_with_minimal_failure
- chain_step_containment | bounded_lift_le_1 -> fails_with_minimal_failure
- chain_step_containment | bounded_lift_le_2 -> fails_with_minimal_failure
- chain_step_containment | chain_step_family -> survives_on_searched_slice

## Minimal failures
- uniqueness_up_to_score_tie_quotient: {"cost": "moved_points_cost", "frontier_ids": ["C2:(0,1)", "C2:(1,1)"], "frontier_size": 2, "model_id": "C2", "profile": "uniform", "slice": "all_monotone_inflationary"}
- uniqueness_up_to_symmetry: {"cost": "moved_points_cost", "frontier_ids": ["B1:(0,1)", "B1:(1,1)"], "model_id": "B1", "profile": "uniform", "slice": "all_monotone_inflationary", "symmetry_class_count": 2}
- benchmark_stability_fixed_cost_tie: {"cost": "moved_points_cost", "model_id": "C3", "profiles": ["uniform", "top_heavy", "bottom_heavy", "middle_heavy"], "slice": "all_monotone_inflationary", "tie": "keep_all_nondominated"}
- cost_stability_fixed_benchmark_tie: {"costs": ["moved_points_cost", "total_rank_lift_cost", "average_rank_lift_cost", "normalized_total_rank_lift_cost"], "model_id": "C3", "profile": "uniform", "slice": "all_monotone_inflationary", "tie": "keep_all_nondominated"}
- chain_step_containment: {"cost": "moved_points_cost", "model_id": "C3", "non_step_frontier_ids": ["C3:(0,2,2)", "C3:(1,1,2)"], "profile": "uniform", "slice": "all_monotone_inflationary", "tie": "keep_all_nondominated"}

## Applicability note
- uniqueness_up_to_symmetry applies to Boolean models only.
- chain_step_containment applies to chain models only.
