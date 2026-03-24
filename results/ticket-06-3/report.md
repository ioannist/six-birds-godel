# Ticket 6.3 Interaction Nontriviality and Anti-Artifact Audit

## Core answers
- Any raw-stability improvement over baseline: yes.
- Programs surviving all artifact flags: baseline_raw, pair__cell_acct_gate__cell_acct_tie_protocol, pair__cell_acct_gate__cell_pkg_gate, pair__cell_acct_tie_protocol__cell_pkg_gate, pair__cell_acct_tie_protocol__cell_pkg_mode_from_acct, pair__cell_pkg_gate__cell_pkg_mode_from_acct, singleton__cell_acct_gate, singleton__cell_acct_tie_protocol, singleton__cell_pkg_gate, singleton__cell_pkg_mode_from_acct.
- Any positive multi-cell interaction gain: yes.
- Best candidate after anti-artifact checks: pair__cell_pkg_gate__cell_pkg_mode_from_acct.

## Artifact distinction
- tie-suppression artifact, quotient-only improvement, hard-coded packaging, and excessive pruning are flagged per program in anti_artifact_summary.json.

## Order sensitivity
- Detected: False.
- Detailed changed contexts are in order_sensitivity.json.
