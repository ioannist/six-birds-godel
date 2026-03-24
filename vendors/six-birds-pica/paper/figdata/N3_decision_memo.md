Q1 Partition competition survival:
At n=256 (k=4, REV excluded), competition-group diffusion misfit relative to full_action is quantified by `Q1_competition_group_vs_full_action_lagr_diff_kl_k4` with delta=-0.03145 and CI=[-0.1032,0.08677].
- Decision: **same** (trace: `Q1_competition_group_vs_full_action_lagr_diff_kl_k4`).

Q2 gen3 vs full_action:
Generator deltas vs full_action are summarized in rows including `Q2_gen3_A13_A14_A19_vs_full_action_tilde_diff_kl` and `Q2_gen4_core_vs_full_action_tilde_diff_kl`; effect signs are mixed but quantifiable with bootstrap CIs.
- Decision: **same** (trace: `Q2_gen3_A13_A14_A19_vs_full_action_tilde_diff_kl`).

Q3 Scale trend direction:
Cross-scale shifts are captured by rows like `Q3_full_action_tilde_geo_r2_delta256m128` and related `Q3_*_delta256m128` entries; trends are configuration-dependent rather than uniformly convergent.
- Decision: **same** (trace: `Q3_full_action_tilde_geo_r2_delta256m128`).

Q4 REV rate at n=256:
Overall REV prevalence at n=256 is reported in `Q4_REV_rate_n256_overall` with rate=0 and Wilson CI=[0,0.01595].
- Decision: **same** (trace: `Q4_REV_rate_n256_overall`).

Q5 Structural interference paradox:
Paradox checks include generator-vs-full_action rows `Q5_gen3_A13_A14_A19_vs_full_action_tilde_frob` and `Q5_gen4_core_vs_full_action_tilde_frob`, plus enabled-count correlation `Q5_spearman_enabledcount_vs_tilde_frob_n256`.
- Decision: **same** (trace: `Q5_gen3_A13_A14_A19_vs_full_action_tilde_frob`).

Caveats:
- Wave_2 truncation persists: 26 logs missing audits, causing incomplete seed coverage in EXP-112 selective n=256 configs.
- Most affected config family: A14_only, A16_only, A17_only, gen3_A13_A14_A19, gen4_core, loo_A13, loo_A14, loo_A18, loo_A19, fa_no_P1row, fa_no_P2mod, fa_no_P3row, baseline, full_action.
- A16_only has the smallest support (5 seeds), and several selective configs have 7-9 seeds rather than 10.
