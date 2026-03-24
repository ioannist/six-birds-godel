# Claim Map Summary (N4)

- Decision add_C7: `False`
- Rationale: N3 decision memo is uniformly 'same' across Q1–Q5; n=256 currently confirms/qualifies existing claims but does not justify a distinct new claim block.
- n256 caveat: Wave_2 has 26 truncated logs missing KEY_AUDIT_JSON; EXP-112 n=256 selective configs have partial seed coverage (min 5, median 8, max 9).

## Claims (strength change)
- C1: `same` | scope_n=[32, 64, 128, 256] | primary=F3, T3, N3
- C2: `same` | scope_n=[32, 64, 128, 256] | primary=F4, T3, N3
- C3: `same` | scope_n=[32, 64, 128, 256] | primary=F5, T6, N3
- C4: `same` | scope_n=[32, 64, 128, 256] | primary=F6, T4, N3
- C5: `not_applicable` | scope_n=[32, 64, 128] | primary=T5, N3
- C6: `same` | scope_n=[32, 64, 128, 256] | primary=T5, N3

## Assets needing n256 update
- F3: sources=['ds_exp112_wave3_n32_64_128_all', 'ds_expf1_wave2_n256_empty', 'ds_exp107_wave2_n256_sweep'] | note=n256 controls are split across EXP-F1/EXP-107 by design.
- F4: sources=['ds_exp112_wave3_n32_64_128_all', 'ds_exp107_wave2_n256_sweep'] | note=n256 panel relies on EXP-107 controls; selective EXP-112 probes incomplete.
- F5: sources=['ds_exp107_wave2_n256_sweep', 'ds_exp112_wave2_n256_selective_unique', 'ds_exp112_wave3_n32_64_128_all', 'ds_expf1_wave2_n256_empty'] | note=n256 is a selected suite (237 runs), not full 69-config census.
- F6: sources=['ds_exp112_wave3_n32_64_128_all', 'ds_exp112_wave2_n256_selective_unique'] | note=n256 supports targeted checks only; full LOO matrix remains n=32/64/128.
- F7: sources=['ds_exp107_wave2_n256_sweep', 'ds_exp112_wave2_n256_selective_unique', 'ds_exp112_wave3_n32_64_128_all', 'ds_expf1_wave2_n256_empty'] | note=n256 tau outcomes available; selective EXP-112 suite has seed gaps.
- F8: sources=['ds_exp107_wave2_n256_sweep', 'ds_exp112_wave2_n256_selective_unique', 'ds_exp112_wave3_n32_64_128_all', 'ds_expf1_wave2_n256_empty'] | note=n256 REV/missingness should be reported with selective-suite caveat.
- T2: sources=['ds_exp107_wave2_n256_sweep', 'ds_exp112_wave2_n256_selective_unique', 'ds_exp112_wave3_n32_64_128_all', 'ds_expf1_wave2_n256_empty'] | note=Must explicitly separate n256 control provenance and selective EXP-112 coverage.
- T3: sources=['ds_exp107_wave2_n256_sweep', 'ds_exp112_wave2_n256_selective_unique', 'ds_exp112_wave3_n32_64_128_all', 'ds_expf1_wave2_n256_empty'] | note=n256 rows should include incomplete-seed annotations for selective configs.
- T4: sources=['ds_exp107_wave2_n256_sweep', 'ds_exp112_wave2_n256_selective_unique', 'ds_exp112_wave3_n32_64_128_all', 'ds_expf1_wave2_n256_empty'] | note=Generator taxonomy should note n256 targeted subset usage.
- T5: sources=['ds_exp112_wave3_n32_64_128_all', 'ds_exp107_wave2_n256_sweep', 'ds_exp112_wave2_n256_selective_unique'] | note=n256 extension likely selective/inconclusive until seed-complete reruns.
- T6: sources=['ds_exp107_wave2_n256_sweep', 'ds_exp112_wave2_n256_selective_unique', 'ds_exp112_wave3_n32_64_128_all', 'ds_expf1_wave2_n256_empty'] | note=Must carry forward 26 truncated-log caveat and per-config seed deficits.

## Mandatory N3 evidence IDs embedded
- Q1_competition_group_vs_full_action_lagr_diff_kl_k4
- Q2_gen3_A13_A14_A19_vs_full_action_tilde_diff_kl
- Q3_full_action_tilde_geo_r2_delta256m128
- Q4_REV_rate_n256_overall
- Q5_gen3_A13_A14_A19_vs_full_action_tilde_frob

## Caveats
- Wave_2 includes 26 truncated logs without KEY_AUDIT_JSON.
- EXP-112 n=256 selective suite has partial seeds (min 5, median 8, max 9).
- n=256 controls are split by provenance: empty from EXP-F1; baseline/full_action/full_all from EXP-107.
