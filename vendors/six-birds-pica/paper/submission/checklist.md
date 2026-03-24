# Submission Dry-Run Checklist (Physica A / Elsevier)

## Section A — Build + integrity
- [x] `make -C paper clean && make -C paper pdf` succeeds (exit 0).
- [x] Undefined citations count = 0.
- [x] Undefined references count = 0.
- [x] `python3 paper/scripts/paper_lint.py` succeeds (exit 0).
- [x] Paper lint summary recorded below.

Commands run:
```bash
make -C paper clean
make -C paper pdf
grep -c "Citation.*undefined" paper/main.log || true
grep -c "Reference.*undefined" paper/main.log || true
grep -c "There were undefined references" paper/main.log || true
python3 paper/scripts/paper_lint.py
python3 paper/scripts/build_flatten_manifest.py
```

Observed outcomes:
- build_exit_code: 0
- undefined_citations_count: 0
- undefined_references_count: 0
- undefined_references_banner_count: 0
- lint_missing_ref_targets: 0
- lint_missing_fig_assets: 0
- lint_missing_bib_keys: 0
- lint_unicode_chars_count: 0
- lint_placeholders_total: 4
- lint_unexpected_placeholders: 0

## Section B — Submission micro-assets (Physica A)
- [x] Highlights file exists: `paper/submission/highlights.txt`.
  - [x] Exactly 5 lines (observed: 5).
  - [x] Each line <= 85 characters (pass).
- [x] Keywords file exists: `paper/submission/keywords.txt`.
  - [x] Exactly 7 keywords (observed: 7).
  - [x] Single-word or hyphenated only (pass).
- [x] AI disclosure file exists: `paper/submission/ai_disclosure.txt`.

Highlights line-length table:

| # | Length | Text |
|---:|---:|---|
| 1 | 72 | Toy universe from a minimal stochastic substrate shows physics-like laws |
| 2 | 82 | Six primitives with 36 interactions define a canonical closure interaction algebra |
| 3 | 77 | Coarse-grained Markov kernels exhibit geometry-like and thermodynamic regimes |
| 4 | 76 | Ablations across 69 interaction subsets reveal minimal generators of regimes |
| 5 | 75 | Coarse-graining can retain irreversibility while dynamics remain stochastic |

## Section C — Compliance statements present in manuscript (Elsevier norms)
- [x] CRediT authorship contribution statement
- [x] Declaration of competing interest
- [x] Funding
- [x] Data availability
- [x] Declaration of generative AI and AI-assisted technologies in the manuscript preparation process
- [x] Acknowledgements
- [x] Acknowledgements is directly before References (bibliography block).

Heading presence proof (in order):
- Introduction
- Methods
- Results
- Discussion
- Conclusion
- CRediT authorship contribution statement
- Declaration of competing interest
- Funding
- Data availability
- Declaration of generative AI and AI-assisted technologies in the manuscript preparation process
- Acknowledgements

## Section D — Figures and tables readiness
- [x] All figure tokens referenced in `main.tex` resolve to assets in `paper/fig/`.
- [x] Figure format is PDF (acceptable for Elsevier submission).
- [x] Figure inventory listed below from refreshed flatten manifest.
- [x] No placeholder figure is referenced in `main.tex`.
- [x] Tables/sections are inline in `main.tex` (no `\input`/`\include` dependencies).

Referenced figure PDFs (24 total):
- [x] `paper/fig/F1_pipeline.pdf`
- [x] `paper/fig/F2_PICA_grid.pdf`
- [x] `paper/fig/F3a_n32.pdf`
- [x] `paper/fig/F3a_n64.pdf`
- [x] `paper/fig/F3a_n128.pdf`
- [x] `paper/fig/F3a_n256.pdf`
- [x] `paper/fig/F3b_n32.pdf`
- [x] `paper/fig/F3b_n64.pdf`
- [x] `paper/fig/F3b_n128.pdf`
- [x] `paper/fig/F3b_n256.pdf`
- [x] `paper/fig/F4a_PLA2_n128.pdf`
- [x] `paper/fig/F4b_step_entropy_n128.pdf`
- [x] `paper/fig/F4c_geo_r2_n128.pdf`
- [x] `paper/fig/F4d_diff_kl_n128.pdf`
- [x] `paper/fig/F4a_PLA2_n256.pdf`
- [x] `paper/fig/F4b_step_entropy_n256.pdf`
- [x] `paper/fig/F4c_geo_r2_n256.pdf`
- [x] `paper/fig/F4d_diff_kl_n256.pdf`
- [x] `paper/fig/F5_regime_scatter_n128.pdf`
- [x] `paper/fig/F5_regime_scatter_n256.pdf`
- [x] `paper/fig/F6_LOO_heatmap.pdf`
- [x] `paper/fig/F7_tau_distribution.pdf`
- [x] `paper/fig/F8_sigma_ratio_distribution.pdf`
- [x] `paper/fig/F8_REV_frequency_heatmap.pdf`

## Section E — Data availability / repository deposit readiness
- [x] Data availability statement is present in manuscript end-matter.
- [ ] DOI placeholder removed (currently `DOI: TBD`) — blocker until replaced.
- [x] Repro package scope is listed (code snapshot, configs/seeds, audits, derived tables, figure/table scripts).

## Section F — Remaining blockers before submission
- token: `TBD` | section: `Front matter (author line)` | why: Author affiliation is required in manuscript metadata. | owner/action: Author — Replace `(affiliation: TBD)` with final affiliation text.
- token: `TODO` | section: `Funding` | why: Funding declaration must be finalized (or explicitly confirmed as none) for submission forms. | owner/action: Author — Replace TODO comment with final funding text (or keep explicit no-funding statement without TODO marker).
- token: `TBD` | section: `Data availability` | why: Repository DOI is required for submission metadata and reproducibility statement finalization. | owner/action: Author — Replace `DOI: TBD` with minted Mendeley Data DOI.
- token: `TODO` | section: `Acknowledgements` | why: Acknowledgements section should be final text or intentionally omitted without TODO marker. | owner/action: Author — Replace TODO comment with acknowledgements text or remove placeholder comment.
