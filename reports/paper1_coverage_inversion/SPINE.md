# Paper 1 — Narrative Spine

**Status:** authoritative skeleton for the structural rewrite (2026-07-16 spine session).
Every rewrite decision defers to this document. If a paragraph, table, or figure does not
serve a claim below, it moves to an appendix or is cut. Exemplar: *Flash Boys 2.0*
(Daian et al.) for shape — name the phenomenon, measure it, argue the infrastructure
stakes, then present the fix. Romano CQR remains the model for §4 only.

---

## 0. The one sentence

> For two-thirds of every week, the reference market for a tokenized equity emits
> nothing — no trades, no quotes, no signal — yet lending protocols value it anyway:
> against a Friday price held flat, synthetic weekend quotes, or a dispersion number
> that collapses to zero at the close, none carrying a verifiable statement of how
> wrong it may be by Monday's open. This paper names that blind window, measures it
> on 12 years of data, and demonstrates an oracle where the consumer picks 95%
> coverage — and can verify they got it.

If a Kamino risk engineer repeats one thing to their team, it is this. The alarm is
carried by the *facts* (emits nothing / held flat / synthetic / collapses to zero —
all documented behaviors), never by adjectives. Every clause survives the
`integrity_issues.md` Tier 2 linter.

## 1. The four claims

Everything in the main text serves one of these. (These reorder and absorb the current
C1–C5; C5/ablation is demoted to supporting evidence for K3.)

- **K1 — The off-hours serving gap is industry-wide, categorizable, and documented
  on tape.** Tokenized equities settle 24/7; their reference markets are closed
  two-thirds of wall-clock time (measured: 639 weekends × 10 symbols 2014–2026,
  22,624 overnight windows). Three sub-claims:
  **(a) Taxonomy** — six serving archetypes spanning oracle types *and versions*
  (stale-hold, bounded-deviation, synthetic-marker, publisher-dispersion,
  executable-overnight, continuous-tracking), characterized from primary
  documentation and wire decoding. A named contribution: the first tape-backed
  taxonomy of off-hours oracle serving behavior.
  **(b) Measurement, where the wire is decodable** — Chainlink v11 weekend bid/asks
  are synthetic bookends (SPYx pure placeholder, QQQx/TSLAx bid-synthetic;
  `marketStatus = 5`, 11 weekends Feb–Apr 2026, `docs/sources/oracles/chainlink_v11.md`
  §3); Pyth feeds are absent near Friday close for 4 of 10 symbols and 22.1%
  available pooled (265/1,200, 2024+, `reports/v1b_pyth_comparison.md`); the full
  k-ladder shows no ex-ante-choosable multiplier on published dispersion yields a
  known coverage level (k=1.96 → 10.2%; the k=50 that realizes 95% is fit in
  hindsight on the evaluation data — attributed to the consumer per P1-16).
  **(c) Adoption asymmetry** — the market trades these assets far more than it
  collateralizes them (>$10B volume vs $186M AUM; conservative reserve configs per
  the 2026-04-26 Kamino snapshot; zero off-hours liquidations), *consistent with*
  unpriced off-hours risk — stated against visible market commitment ($29B tokenized
  RWA, BUIDL live as collateral, exchanges filing for 24h sessions), which is what
  makes the gap glaring rather than niche.
  *(Guardrails: (i) taxonomy is complete, measurement is partial — T1 carries a
  per-row "measured on tape / characterized from documentation" flag so no
  measurement is implied that we don't have; (ii) the word is "adoption asymmetry,"
  never "mistrust" — no psychological diagnosis, "consistent with" framing, every
  figure cited (P1-10); (iii) describe feed mechanics factually — NEVER attribute a
  coverage claim to an incumbent; none makes one.)*
- **K2 — Coverage inversion is the fix, as an interface not a promise.** Invert the
  oracle contract: target coverage τ is the consumer-chosen input, the band is the
  output, and every read carries a receipt (τ, c(τ), q_r(τ), σ̂_s, regime) any third
  party can re-derive from public data. Calibration becomes auditable, SLA-shaped.
- **K3 — A simple, fully-disclosed architecture delivers the contract.** Locally-weighted
  Mondrian split-conformal: LOSO coverage 0.9497 ± 0.0128 (10/10 Kupiec), nested
  temporal holdout 0.9504, 40/40 Kupiec on the symbol × τ grid vs GARCH-t's 31/40;
  generalizes to overnight gaps with only the gap selector changed; and because
  earnings are publicly dated, the band widens *ahead* of them and stays calibrated
  against an ~8× tail — calendar-conditioned coverage, which no incumbent surface has.
- **K4 — The failure mode is disclosed and turned into a product feature.** Pooled DQ
  rejects: bands are per-anchor, not full-distribution, calibrated. The residual is
  within-weekend cross-sectional co-breach, quantified into reserve guidance
  (k* = 3 at τ = 0.95). Only a calibration-transparent oracle can publish this
  measurement at all — honesty is the moat, not a caveat.

## 2. Section skeleton (~10,000 words main text)

One sentence per section = what the section must prove. Budget is a ceiling.

| § | Title | One sentence | Budget | Draws from |
|---|-------|--------------|--------|------------|
| — | Abstract | The one sentence + K2 + the three strongest numbers of K3 + K4 in one clause each. | 200 | 00 (rewrite) |
| 1 | The blind window | Market commitment (cited: ~$29B tokenized RWA, BUIDL as collateral, 24h-exchange filings) → measured gap tails → **§1.2 "What the window serves": the K1 taxonomy (six archetypes × measured-or-characterized, T1) with tape findings (synthetic markers, availability 22.1%, k-ladder) and sample bounds inline** → the adoption asymmetry (AUM≪volume, conservative configs, zero off-hours liquidations, "consistent with") → coverage inversion preview + contributions (K1 taxonomy named first). | 2,400 | 01, `active/economic_motivation_draft.md`, `v1b_pyth_comparison.md`, `docs/sources/oracles/chainlink_v11.md`, fig0→H1 |
| 2 | Related work | Position against (a) conformal prediction, (b) VaR backtesting, (c) oracle designs — one paragraph each; the intersection is empty. | 900 | 02 (compress 60%) |
| 3 | The primitive | Formal contract: calibration surface, inversion, PricePoint receipt, properties P1–P3, non-goals. | 1,200 | problem_statement (keep shape, trim P2 caveats to appendix) |
| 4 | Architecture | The recipe a reader could reimplement: regime labeler → per-symbol σ̂ standardization → per-regime conformal quantiles → buffer c(τ) → serving lookup. | 1,500 | 04, fig H2 |
| 5 | Data | Panel construction, regimes, and the forward-tape harness in one page. | 700 | 05 (compress) |
| 6 | The contract holds | K3's evidence in claim order: LOSO + temporal holdout → master grid vs baselines → tokenized-tracking head-to-head (one paragraph; see promotion note below) → overnight generalization → earnings nights. One table (master grid), three figures. | 1,800 | 06 (cut ~75%; §6.1–6.2, 6.3.2, 6.3.6, 6.5 → appendix), 07 §7.6.3/7.6.5 headline |
| 7 | What is load-bearing | Compact ablation: stratification, σ̂ standardization, selection procedure — effect sizes only, ladder to appendix. | 700 | 07 (cut ~85%) |
| 8 | Where it fails | K4: DQ rejection, co-breach topology, k* = 3 reserve guidance, BoJ weekend as the worst case, then remaining limitations honestly. | 900 | 06.3.4–6.3.5, 09 (cut ~75%) |
| 9 | Conclusion + extensions | The primitive stands independent of this architecture; what a conformalized upgrade and a protocol integration would take. | 400 | 10, 11 |
| A– | Appendices | Reproducibility, full validation battery, simulation study, σ̂ ladder, serving layer (current §8), extended diagnostics. | uncapped | 12, 08, cut material |

Current §8 (serving layer) leaves the main text: it is engineering, not evidence —
two paragraphs of it survive inside §4 ("this is deployed; Python/Rust/Anchor"), rest
to appendix. The chronology of what was tried stays in `methodology_history.md`.

## 3. Hero figures

Each carries exactly one claim. Main text gets ≤7 figures total.

| Fig | Claim | Content | Status |
|-----|-------|---------|--------|
| H1 | K1 | **The blind window.** Wall-clock week colored by reference-market state, with the realized close→open gap distribution (weekend vs overnight vs earnings-night) overlaid. The stakes picture. | NEW (upgrade fig0) |
| H2 | K2 | **Anatomy of a read.** Consumer-facing: τ goes in → band + receipt comes out → third party re-derives the surface from public data and checks. The method-as-product diagram. | NEW (fig1 is internal pipeline; keep fig1 in §4) |
| H3 | K3 | **The money plot.** Realized vs target coverage across τ and regimes, deployed vs GARCH-t (merge fig2 + fig5 into one panel if possible). | EXISTS (fig2, fig5) |
| H4 | K3 | **Calendar-conditioned coverage.** Earnings event study: band widens before the release, calibrated against the 8× tail. | EXISTS (fig11) |
| H5 | K4 | **The joint tail.** k_w distribution vs independence strawman vs t-copula, k* = 3 marked, BoJ weekend annotated. | EXISTS (fig10) |
| S1 | K3 | Per-symbol 40/40 grid (supporting, §6). | EXISTS (fig4) |
| S2 | K3 | Overnight calibration (supporting, §6). | EXISTS (fig8) |

fig6 (path coverage), fig7b (ablation), fig9 (BoJ anatomy), simulation_summary →
appendix. fig9's content is summarized in one §8 paragraph.

**Table T1 (§1.2, not a figure):** the six archetypes × columns: mechanics ·
**evidence class ("measured on tape" / "characterized from documentation")** ·
finding · sample bounds. Sources: current §1.1 archetype table + imports from
`reports/v1b_pyth_comparison.md` (availability row: 22.1% pooled, 0% for
AAPL/GOOGL/HOOD/NVDA; k-ladder finding) + `docs/sources/oracles/chainlink_v11.md`
§3 (synthetic markers). Caption bounds: Kamino Open/AllUpdates per-reserve mode is
governance-mutable and undecoded (09:96). Attribution template: fig5's caption
sentence. This is the damning table; it must read as a lab report, not an editorial.

**§6 promotion (LOCKED 2026-07-16):** one ~100-word paragraph after the
GARCH-t comparison — the tokenized-tracking baseline head-to-head (−45% half-width,
−46% Winkler at matched coverage; 7-of-9 per-symbol with the SPY/TSLA concession
stated). Framing guardrails: it is a *constructed proxy* for the continuous-tracking
archetype following Cong's published passthrough (λ=0.903), not any vendor's product
— say so explicitly; construction + power caveat stay in App-D; numbers do NOT enter
the master-grid table (different panel, n=117).

## 4. Voice rules for the rewrite

1. Claims first, evidence second, chronology never. "We show X (Table 2)" not
   "We first tried A, then B."
2. Every number in the main text appears because a claim needs it. The validation
   battery exists to be *cited*, not *walked through*.
3. Incumbent descriptions are factual mechanics only (see K1 guardrail).
4. Gloss econometric terms on first use (Kupiec = binomial test of violation rate;
   DQ = regression test that violations are unpredictable). The AFT reader is a
   protocol engineer, not an econometrician.
5. The word "receipt" is the product metaphor — use it consistently; drop synonyms.
6. **Damning-but-factual.** The stakes section is allowed to alarm, but every alarming
   statement must be a measured finding with its sample bounds in the same sentence
   (11 weekends, Feb–Apr 2026, `marketStatus = 5`, …) and correct attribution (the
   σ-misread belongs to the consumer, not Pyth). Adjectives, causal claims about
   protocol losses, and AUM-pitch framing are banned — `integrity_issues.md` Tier 2
   (P1-08 through P1-16) is the linter for this section, and the rewrite must not
   reintroduce anything that log already struck.

## 5. Process from here

- **Step 2 — reverse-outline:** subagents map every paragraph/table/figure of the
  current draft to a skeleton slot, appendix, or cut. Output: a disposition table.
- **Step 3 — rewrite:** one subagent per section against this spine + voice rules,
  Adam reviews each section against its one sentence and budget.
- **Step 4 — adversarial review:** only after structure is fixed.
