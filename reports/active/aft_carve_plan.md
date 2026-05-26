# AFT 2026 carve plan — 20-page LIPIcs main text + appendix

**Status:** plan (2026-05-25), pending AFT chair reply on the deadline. **Source of truth** for slimming the 57-page technical report into an AFT conference paper.

## Governing facts (from the CFP, verified)
- **≤20 pages of text** in **LIPIcs format**, **excluding title page and bibliography**.
- **Appendices do NOT count** toward the 20 pages and are *read at reviewers' discretion*; authors may point to a "full version" for appendices beyond 20pp.
- Single-blind, **anonymized** title page; third-person self-reference.
- Format: Dagstuhl `lipics-v2021.cls` (not the arXiv/NIPS template).

## Strategy: relocate, don't cut
The arXiv version (built, `--arxiv`) **is** the full version. The AFT submission =
**a self-contained 20pp conference paper** + an appendix that is essentially today's
depth. No analysis is deleted; content is re-tiered main↔appendix. Decision (2026-05-25):
**keep a ~1.5pp system slice in main text** (§8.1 split-by-function + byte-parity receipt
+ §8.7 practitioner τ→reserve) — the deployable/on-chain angle is the AFT differentiator.

## Page budget (main text, target ≈20pp incl. ~4 figures)

| Section | Budget | Keep in main text | → Appendix |
|---|---:|---|---|
| §1 Introduction | 2.0 | motivation, 68%-hours gap, the inversion, off-hours + calendar-conditioned contribution | — |
| §2 Related work | 1.0 | categorical claim (no incumbent publishes a coverage receipt) + key cites | full 28-ref survey |
| §3 Problem statement | 1.5 | coverage-inversion formalism, two closed-market panels | — |
| §4 Methodology | 3.0 | point, σ̂, Mondrian conformal, c(τ), serving formula, §4.3.1 earnings_night/calendar-conditioned | — |
| §5 Data | 1.25 | universe, weekend + overnight panels, train/test split | §5.4 switchboard tables, §5.7 provenance |
| §6 Results | 4.5 | §6.3.1 headline table, §6.3.3 LOSO + temporal holdout, §6.4.1 per-symbol, §6.4.3 GARCH-t, §6.5 path (brief), §6.8 off-hours | §6.3.2/4/5/6, §6.4.2/4, §6.6 detail, §6.7 detail |
| §7 Ablation | 1.5 | the 3 load-bearing components + §7.6 SPY/TSLA tie | all sub-subsections |
| §8 Serving | 1.5 | §8.1 architecture, §8.5 byte-parity receipt, §8.7 practitioner τ→reserve | §8.2/8.3/8.4 crate table + wire format |
| §9 Limitations | 1.25 | DQ/per-anchor-not-full-distribution, portfolio solvency (§9.4), scope (§9.8), OOS-tuned c(0.95) (§9.3) | the other ~7 disclosures |
| §10 Future work | 0.5 | the 2–3 named residual fixes | roadmap detail |
| §11 Conclusion | 0.75 | tight | — |
| **figures (≈4)** | ~1.5 | fig1 pipeline, fig2 calibration, fig8 overnight-calibration, fig5 pareto *(or fig4 per-symbol)* | fig0, fig3, fig4/5 (whichever not kept), fig6, simulation_summary |
| **total** | **≈20.25** | | |

Figures are the tightest lever — keep ~4 in main text, the rest to appendix. Trim §6 first if over.

## Appendix structure (unbounded; the report's depth)
A (Reproducibility, current §12) · B (full §6 diagnostics: tertile, joint-tail, worst-weekend, DQ/Berkowitz, master grid, forward-tape, simulation) · C (full ablation sub-analyses) · D (system internals: crate stack, wire format, parity) · E (the remaining §9 disclosures) · F (full related-work survey). Point to the arXiv "full version" for anything beyond.

## Mechanics / open work (gated on AFT go-ahead)
1. **LIPIcs template** — new pandoc template targeting `lipics-v2021.cls` + the LIPIcs author/affiliation/CCS-subject/keyword macros. One-time.
2. **Anonymization** — strip `\author` block, third-person self-reference, repo URL → "anonymized for review" (arXiv version keeps attribution).
3. **Build mode** — `build.py --aft`: a separate `SECTION_ORDER` of *condensed main-text* section files + an appendix bundle, feeding the LIPIcs template. Parallel to `--arxiv`; both regenerate from the same source pool so the versions don't drift.

## Sequencing recommendation
- **Now (venue-independent):** lock this content triage. Optionally pre-draft the condensed §1/§2/§6 main-text prose — reusable for AFT *or* any conference carve.
- **Hold until AFT replies:** the LIPIcs template, anonymization, and `--aft` build wiring — wasted effort if this slips to AFT 2027 or a different venue (e.g. FC), which would change the format target. The content triage above survives any of those outcomes.
