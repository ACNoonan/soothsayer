# Pitch deck content — pending additions

**Status:** drafted 2026-04-25, not yet incorporated into `landing/pitch.html` or `landing/index.html`.
**Source conversation:** Q&A with Claude on "if it's so obvious, why doesn't it exist?" — captured here as canonical slide drafts.

This doc holds two slide drafts that should land in the deck and the landing page. They are *additive* — the existing slide 03 ("Why now") is a market-tailwind slide ($25B volume, $26.4B RWA, Chainlink admission). These two are a structural-reasons slide and a why-us slide that sit alongside it.

## Where each slide goes

| Slide | Target in `landing/pitch.html` | Target in `landing/index.html` |
|---|---|---|
| **Why this gap is still open** | New slide between current `03 — Why now` and `04 — Used-car-lot analogy`, OR fold into bottom of slide 03 as a second panel | Add as a new band between `#gap` and `#product`, framed as "why this gap persists" |
| **Why an ML engineer found this — not a quant** | New slide near the back of the deck (before or after `10 — Risks`); reads as a founder/insight slide | Add to a future founder/about section, or as a sidebar paragraph in the methodology band (`#method`) |

---

## Slide A — Why this gap is still open

**Headline:** *The pieces only finished arriving in 2025–26.*

**Sub:** *Decentralized oracles + tokenized RWAs + DeFi model-risk discipline. The window opened ~18 months ago.*

**Body (4–5 bullets, pick whichever land best in deck rhythm):**

- **Oracles were built as point feeds, not risk objects.** Chainlink's median-of-N design is optimized for `if (price < threshold)` in a smart contract. Probability never had an interface.
- **Pyth ships a σ but won't promise calibration.** Their confidence is publisher-dispersion, not realized coverage. They explicitly avoid the calibration claim — because once you make it, you're falsifiable.
- **Opaque providers face a backwards incentive.** RedStone and similar 24/7 feeds could have shipped this years ago. Calibration evidence is a *liability*, not a feature, when buyers don't yet demand auditability.
- **The buyer side wasn't ready.** Calibrated feeds are valuable to risk managers. DeFi protocols didn't have an MRM function until ~2025. SR 26-2 (April 2026), MiCA, and Aave/Morpho/Kamino building risk teams are forcing institutional discipline now.
- **The data wasn't bridgeable.** xStocks are ~3 months old. Without a factor-switchboard mapping to 12 years of underlying-equity history, the calibration surface couldn't be built.

**Kicker:** *Tokenized RWAs at scale + DeFi MRM emerging + ML calibration vocabulary spreading + a regulatory tailwind. Most oracle teams are still optimizing point estimates.*

---

## Slide B — Why an ML engineer found this, not a quant

**Headline:** *This product is a port, not an invention.*

**Sub:** *The domain it was ported from is ML deployment, not financial econometrics.*

**Body:**

- **Customer-picks-coverage has a name in ML: conformal prediction** (Vovk 2005; Romano-Patterson-Candès 2019). Over the last ~5 years it became the standard pattern for shipping ML models with calibrated uncertainty: the model takes α as a request parameter and returns a calibrated set.
- **Quants reach for parametric.** Trained on Black-Scholes, delta-normal VaR, Gaussian residuals. Seeing Pyth's σ, they assume calibration is implied — because in *their* world, σs always are. They optimize point forecasters because that's what the literature rewards.
- **ML engineers reach for empirical.** Trained on held-out evaluation, ablation tables, bootstrap CIs. Seeing Pyth's σ, my first question was: *what's the realized coverage on a held-out window?* Nobody publishes it. That gap is the entire product.
- **The validation methodology reflects the same lineage.** Block-bootstrap CIs, 2023+ held-out OOS slice, ablation table isolating each component, conformal baselines evaluated as comparators. ML-deployment hygiene, not classical econometric hygiene.
- **The simple forecaster underneath is on purpose.** Factor-switchboard + log-log vol regression is deliberately boring. The contribution is the *primitive* that surrounds any forecaster — exactly the way conformal prediction is model-agnostic.

**Kicker:** *Quants in oracles optimize point estimates. Soothsayer makes the calibration the product. The reframing was hiding inside a five-year-old ML deployment pattern — visible to an outsider fluent in it.*

---

## Pairing notes for the deck

- **Adjacency.** Slide A → Slide B reads as one argument: the gap exists for structural reasons, and the founder's specific lens is what made the gap visible. Stronger as a pair than either alone.
- **Cite the conformal lineage by name.** Vovk 2005, Romano-Patterson-Candès 2019. Investors who've seen ML decks will recognize it; investors who haven't will Google and find a respectable academic backbone.
- **Resist novelty claims on the math.** The deck is stronger if it explicitly says "the forecaster is boring on purpose; the primitive is the contribution." Sophisticated investors reward that self-awareness.

## Cross-references

- Conversation source: 2026-04-25 Claude session on user-facing explanations and "why doesn't this exist."
- Underlying claims grounded in: `reports/v1b_decision.md`, `reports/v1b_calibration.md`, `reports/v1b_ablation.md`, `reports/v1b_conformal_comparison.md`, `reports/paper1_coverage_inversion/01_introduction.md`.
