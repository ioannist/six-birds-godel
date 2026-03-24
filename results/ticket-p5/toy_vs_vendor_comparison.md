# Ticket P5 Toy-vs-Vendor Comparison

## Scope
- Inputs: `data/pica_atlas/*`, `data/pica_normalized/*`, and existing toy reports (`results/ticket-05` through `results/ticket-06-4`).
- Method: conservative support/provenance comparison only (no new runs, no claim promotion).

## Comparison
- baseline-like configs vs richer structured configs: **supported_by_vendor** (baseline/full_action/full_all and row/group surfaces are all shipped and parsed).
- heterogeneous cell importance: **supported_by_vendor** (LOO + row/group coverage is non-uniform in shipped program atlas).
- interaction structure appears necessary: **supported_by_vendor (cautious)** (robustness/ablation surfaces are present; effect-size promotion deferred).
- broad uniqueness/stability-style claims: **not_assessable_from_shipped_data** (toy falsification exists, but no direct normalized vendor metric mapping for full equivalence test).

## Caution
- Any statement above marked supported is support at the surface/provenance level, not a promoted theorem-level conclusion.
