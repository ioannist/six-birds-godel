# Ticket 6.2 PICA-lite Interaction Audit

## Core answer
- Any program improving over baseline_raw: yes.
- Improving programs: accounting_core, chain_step_fallback, combined_core, combined_minus_acct_gate, combined_minus_acct_tie_protocol, combined_minus_lens_protocol, combined_minus_pkg_gate, combined_minus_pkg_mode_from_acct, combined_minus_pkg_rewrite, lens_protocol_core, packaging_core.

## Ablation signal
- cell_acct_tie_protocol: delta_instability_when_removed=0.316261
- cell_pkg_gate: delta_instability_when_removed=0.016590
- cell_pkg_mode_from_acct: delta_instability_when_removed=0.016590
- cell_lens_protocol: delta_instability_when_removed=0.000000
- cell_acct_gate: delta_instability_when_removed=-0.029199
- cell_pkg_rewrite: delta_instability_when_removed=-0.079822

## Trivial-collapse check
- accounting_core: pool_ratio_vs_baseline=0.4260, possible_trivial_collapse=False
- baseline_raw: pool_ratio_vs_baseline=1.0000, possible_trivial_collapse=False
- chain_step_fallback: pool_ratio_vs_baseline=0.6686, possible_trivial_collapse=False
- combined_core: pool_ratio_vs_baseline=0.2829, possible_trivial_collapse=False
- combined_minus_acct_gate: pool_ratio_vs_baseline=0.3322, possible_trivial_collapse=False
- combined_minus_acct_tie_protocol: pool_ratio_vs_baseline=0.2829, possible_trivial_collapse=False
- combined_minus_lens_protocol: pool_ratio_vs_baseline=0.2829, possible_trivial_collapse=False
- combined_minus_pkg_gate: pool_ratio_vs_baseline=0.3224, possible_trivial_collapse=False
- combined_minus_pkg_mode_from_acct: pool_ratio_vs_baseline=0.3224, possible_trivial_collapse=False
- combined_minus_pkg_rewrite: pool_ratio_vs_baseline=0.3125, possible_trivial_collapse=False
- lens_protocol_core: pool_ratio_vs_baseline=1.0000, possible_trivial_collapse=False
- packaging_core: pool_ratio_vs_baseline=0.3322, possible_trivial_collapse=False

## Interpretation
- Improvements are interaction-profile dependent and evaluated against baseline_raw.
- Collapse flags indicate where stability gains may come mostly from heavy candidate pruning.
