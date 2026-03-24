# Ticket 05 Counterexample Search

## Search Space
- C2: 2 monotone inflationary self-maps
- C3: 5 monotone inflationary self-maps
- C4: 14 monotone inflationary self-maps
- C5: 42 monotone inflationary self-maps
- C6: 132 monotone inflationary self-maps
- B1: 2 monotone inflationary self-maps
- B2: 9 monotone inflationary self-maps
- B3: 216 monotone inflationary self-maps
- Total operators checked: 422

## Conjecture Outcomes
- Uniqueness: counterexample found
- Reweighting stability: counterexample found
- Canonical step-family on chains: counterexample found

## Minimal Examples
- Uniqueness: {"frontier_ids": ["B1:(0,1)", "B1:(1,1)"], "frontier_size": 2, "model_id": "B1", "profile": "uniform"}
- Reweighting stability: {"bottom_heavy": ["B2:(0,1,2,3)", "B2:(0,1,3,3)", "B2:(0,3,2,3)", "B2:(1,1,3,3)", "B2:(1,3,3,3)", "B2:(2,3,2,3)", "B2:(2,3,3,3)"], "model_id": "B2", "top_heavy": ["B2:(0,1,2,3)", "B2:(0,1,3,3)", "B2:(0,3,2,3)", "B2:(0,3,3,3)", "B2:(1,3,3,3)", "B2:(2,3,3,3)"], "uniform": ["B2:(0,1,2,3)", "B2:(0,1,3,3)", "B2:(0,3,2,3)", "B2:(0,3,3,3)", "B2:(1,1,3,3)", "B2:(1,3,3,3)", "B2:(2,3,2,3)", "B2:(2,3,3,3)"]}
- Canonical step-family on chains: {"model_id": "C3", "non_step_frontier_ids": ["C3:(0,2,2)", "C3:(1,1,2)"]}
