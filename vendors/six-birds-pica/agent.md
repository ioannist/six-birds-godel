# Agent Operating Manual — Day-to-Day Loop Script

## Purpose

This is the self-prompt operating manual for iterative theory-building in the Six Birds
Emergence Ladder. Follow this loop exactly. Each iteration must produce one of:
- a falsified hypothesis,
- a refined hypothesis,
- a verified closure,
- or a tooling improvement that unblocks verification.

## The Iteration Loop

```
1.  SELECT TARGET LAYER: L
2.  SELECT INPUT CLOSURES: C(L)
3.  GENERATE 3-10 CANDIDATE HYPOTHESES (primitive-only compositions)
4.  PICK THE SMALLEST FALSIFIABLE HYPOTHESIS: H*
5.  DESIGN MINIMAL EXPERIMENT: E* (include sweeps + metrics)
6.  IMPLEMENT E* (smallest code change)
7.  RUN E* locally (seeded)
8.  ANALYZE METRICS
9.  DECISION:
    - If closure candidate: run robustness sweep, then promote to closure
    - Else: record falsification/refinement
10. WRITE LEDGER ENTRIES (hypothesis, experiment, result)
11. UPDATE LAYER NOTES
12. CHOOSE NEXT STEP (new hypothesis or new layer)
```

## Stop Conditions

An iteration is complete when ANY of these hold:
- You have recorded results and updated the ledger, OR
- You have created/updated a closure entry, OR
- You have identified an unblocked unknown and registered a "Resolution Experiment".

## How to Select Next Hypotheses

Priority order:
1. **Resolution experiments** for UNKNOWN_TODOs that block current layer progress.
2. **Smallest falsifiable claim** about current layer closures.
3. **Composition experiments**: apply a new P1-P6 operation to existing closures.
4. **Cross-layer experiments**: test if a layer N closure enables a layer N+1 structure.

Generation rules:
- Every hypothesis must reference ONLY primitives P1-P6 and prior accepted closures.
- If a hypothesis requires a concept not yet derived, it must be decomposed until
  each sub-claim uses only primitives + closures.
- Prefer hypotheses that are:
  (a) falsifiable by a small experiment,
  (b) informative regardless of outcome,
  (c) not duplicating a prior experiment.

## How to Promote Closures to the Next Layer

1. Candidate identified: a pattern is stable under generating operators.
2. **Stability sweep**: run 10+ seeds at fixed scale, check tolerance epsilon.
3. **Robustness sweep**: vary scale parameter across 3+ orders of magnitude.
4. Both pass => record in `lab/ledger/closures.jsonl` and copy to
   `lab/layers/layer_N/closures.json`.
5. Write human-readable summary in `lab/layers/layer_N/notes.md`.
6. The closure is now available as input for layer N+1 hypotheses.

## How to Prevent Assumption Creep

Before writing any code or hypothesis, check:

- [ ] Does this use ONLY P1-P6 operations on the substrate?
- [ ] Does this use ONLY closures from prior layers as input objects?
- [ ] Am I importing any meaning (geometry, counting, fields, etc.) that hasn't been
      earned through experiments?
- [ ] Is my "observation" or "measurement" implemented as a lens (deterministic map)?
- [ ] Am I using an external schedule? (If yes, encode phase-in-state per A_AUT.)
- [ ] Is my audit monotone under coarse-graining? (No false positives under lenses.)

If any check fails, decompose the hypothesis further or register an UNKNOWN_TODO.

## Template: Hypothesis Entry

```json
{
  "id": "HYP-###",
  "layer": 0,
  "status": "proposed",
  "claim": "Given closures [...] and primitive P#, composition X produces pattern Y stable under sweep S",
  "primitives_used": ["P5"],
  "input_closures": [],
  "falsification_criterion": "Pattern Y does not appear or is unstable across seeds",
  "proposed_experiment": "EXP-###",
  "timestamp": "ISO-8601"
}
```

## Template: Experiment Entry

```json
{
  "id": "EXP-###",
  "hypothesis_id": "HYP-###",
  "status": "planned",
  "description": "...",
  "parameters": {"seed_range": [0, 9], "scale_range": [4, 64], "steps": 100},
  "metrics": ["metric_name"],
  "artifacts_dir": "lab/artifacts/EXP-###/",
  "timestamp": "ISO-8601"
}
```

## Template: Result Entry

```json
{
  "id": "RUN-EXP-###-seed-scale-hash",
  "experiment_id": "EXP-###",
  "seed": 42,
  "scale": 8,
  "params": {},
  "metrics": {"metric_name": 0.0},
  "artifacts": ["lab/artifacts/EXP-###/RUN-.../metrics.json"],
  "outcome": "falsified|supported|inconclusive",
  "timestamp": "ISO-8601"
}
```

## Daily Checklist

Before starting:
1. Read `lab/ledger/hypotheses.jsonl` — what's open?
2. Read current layer's `notes.md` — what's the state of play?
3. Check UNKNOWN_TODOs in `theory/primitives.yaml` — any unblocked?

After each iteration:
1. Ledger updated? (hypothesis + experiment + result entries)
2. Layer notes updated?
3. Artifacts saved and reproducible?
4. No assumption creep? (run the checklist above)
