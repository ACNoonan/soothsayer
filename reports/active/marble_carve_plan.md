# MARBLE 2026 carve plan — 8-page LNCS short paper (theory-forward)

**Status:** plan (2026-05-25). Third target after arXiv (full) and AFT (20pp LIPIcs).

## Governing facts (from the CFP, verified)
- **Short paper ≤ 8 pages INCLUDING references**, **LNCS format** (Springer `llncs.cls`).
- **Deadline 14 June 2026** (AoE); notification 31 July; camera-ready 23 Aug; conf 16–18 Sep, Cyprus.
- **Double-blind** — fully anonymized, no identifying info.
- Scope: *"mathematics behind blockchain… cryptoeconomics, game-theoretic analysis… emphasizing theoretical foundations rather than business applications."*

## Strategy: theory-forward, ~2.5× tighter than the AFT main text
MARBLE rewards the *formalism and the guarantee*, not the market narrative. So this version foregrounds **coverage-inversion as a formal oracle primitive (§3)** and **the split-conformal calibration construction + its finite-sample guarantee (§4)**; the empirical battery is supporting evidence, and the system/practitioner material is nearly cut. The economic motivation collapses to a *single* compact paragraph (the off-hours-vacuum hook — `reports/active/economic_motivation_draft.md`), not the centerpiece. Reuses the AFT condensed sections (`aft/`), compressed further.

## Page budget (~7pp text + ~1pp refs, LNCS density)

| Section | Budget | Content |
|---|---:|---|
| §1 Introduction | 0.75 | off-hours-vacuum hook (1–2 sentences) → the inversion → contribution. Minimal market-size. |
| §2 Related work | 0.5 | categorical claim (no incumbent publishes a coverage receipt) + conformal/calibration lineage cites |
| §3 Problem statement | **1.25** | the formal coverage-inversion definition, properties $P_1$–$P_3$, the two closed-market panels — *the theory core MARBLE wants* |
| §4 Methodology | **1.5** | factor-adjusted point, per-symbol σ̂ standardisation, Mondrian split-conformal + within-category finite-sample validity, $c(\tau)$; earnings_night/calendar-conditioned in one para |
| §5 Data | 0.4 | universe, both panels, split — terse |
| §6 Results | 1.5 | the two pooled coverage tables (weekend + overnight), LOSO, the 40-cell grid headline, the DQ residual |
| §7 Ablation | 0.4 | the three load-bearing components in one compressed paragraph |
| §8 Serving | 0.25 | one paragraph (auditability + byte-parity receipt); practitioner bridge dropped (theory venue) |
| §9 Limitations | 0.4 | per-anchor-not-full-distribution + scope only |
| §10/§11 | 0.25 | one paragraph each |
| references | ~1.0 | trimmed to the cited subset |

No appendix (8pp is the whole artifact; point to the arXiv full version for everything else).

## Mechanics
1. **LNCS template** — `llncs.cls` (check `kpsewhich llncs.cls`; Springer class, usually in TeX Live). New pandoc template with the LNCS `\institute`/`\author`/abstract/keywords macros; **anonymized** (`\author{Anonymous}`, no repo URL, third-person).
2. **Build mode** — `build.py --marble`: an even-more-condensed `marble/` section set (or reuse `aft/` with further-trimmed §3/§4/§6) feeding the LNCS template. Parallel to `--aft`.
3. **Emphasis shift vs AFT:** §3+§4 get *more* relative weight (the math); §8 practitioner bridge and §6 diagnostics get cut hardest.

## Sequencing
- **14 June is the nearest real deadline** — if pursuing MARBLE, this is the critical path.
- Reuses the `aft/` condensed sections; the additional work is: further-trim §3/§4 (currently full in the AFT build) into theory-tight `marble/` versions, the LNCS template, and anonymization. The economic-motivation and off-hours-vacuum content (just drafted) is already shared across all three versions.
- Honest scope check: MARBLE's "theory over business applications" lean means the *empirical* nature of this paper (a measurement/calibration study) is a moderate fit, not a perfect one — the conformal-guarantee framing is what carries it there. Worth weighing whether MARBLE or a more applied venue (FC, AFT) is the better second home before investing the LNCS carve.
