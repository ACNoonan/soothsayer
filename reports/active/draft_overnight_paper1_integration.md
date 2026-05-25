# DRAFT — Paper 1 fold-in: off-hours generalisation + earnings_night

**Status:** draft for review (2026-05-25). Standalone paper-voiced text for the
overnight fold-in decided this session. Once approved, thread into the live
sections per the checklist at the end. Numbers from
`reports/active/overnight_calibration_firstread.md` (reproducible via
`scripts/build_overnight_panel.py` + `scripts/build_overnight_artefact.py`).

---

## A. Proposed new §6.8 — Off-hours generalisation: overnight gaps

*(insert after §6.7 simulation study; renumber current §6.8 Summary → §6.9)*

§6.2–§6.7 validate the architecture on the **weekend** gap — the ~65-hour
Friday-close → Monday-open window. The closed-market problem it addresses,
however, recurs every trading night: the ~17-hour close → next-open window when
the US venue is shut but overseas markets and index futures continue to price
the underlier. If calibration-transparency is a property of the *method* and not
an artefact of the weekend, the same architecture should calibrate on overnight
gaps. We test this directly.

We rebuild the panel with a single change — the gap selector admits
consecutive-trading-day pairs (`gap == 1`) rather than Friday→Monday pairs —
yielding **22,624 overnight rows across 2,412 weeknights** on the same ten
tickers, 2014-01-16 → 2026-04-23 (≈3.8× the weekend panel). Every downstream
component (factor-adjusted point, per-symbol $\hat\sigma_s(t)$, Mondrian
split-conformal, OOS-fit $c(\tau)$) is gap-length-agnostic and is reused
unchanged; the weekend results of §6.2–§6.7 are byte-identical under the default
selector. The regime set is re-derived for the overnight cadence (§4.3 addendum):
`long_weekend` has no analog and is dropped, `high_vol` is retained with a
252-trading-day VIX lookback, and an **`earnings_night`** regime is added (§B).

**Pooled OOS conditional coverage (overnight; train < 2023-01-01, 16,094 rows;
OOS ≥ 2023-01-01, 6,450 rows × 645 nights):**

| $\tau$ | Violations | Rate | Kupiec $p_\text{uc}$ | Christoffersen $p_\text{ind}$ | $c(\tau)$ |
|---:|---:|---:|---:|---:|---:|
| 0.68 | 2,062 | 0.320 | 0.957 | 0.573 | 1.019 |
| 0.85 |   965 | 0.150 | 0.931 | 0.243 | 1.000 |
| **0.95** | **311** | **0.048** | **0.509** | **0.165** | **1.000** |
| 0.99 |    52 | 0.008 | 0.105 | 1.000 | 1.000 |

**Kupiec and Christoffersen pass at every served anchor.** This is the same
headline property as the weekend panel (§6.3.1), reproduced on a different and
materially larger panel, and the OOS-fit $c(\tau)$ collapses to ≈1.0 — the
overnight bands need essentially no post-hoc widening to calibrate.

**Robustness to consecutive-night autocorrelation.** Overnight gaps, unlike
weekends, are temporally adjacent, so the i.i.d. assumption behind Christoffersen
is more strained. A moving-block-bootstrap on the OOS violation series (block
lengths $L \in \{1, 5, 10\}$, 2,000 reps) places the nominal violation rate
$1-\tau$ inside the 95% CI at every $\tau$ and every block length, and the CIs
barely widen from the i.i.d. case ($L=1$) to $L=10$ (e.g. $\tau = 0.95$:
$[0.043, 0.054]$ at $L=1$ vs $[0.043, 0.054]$ at $L=10$, nominal 0.05). The
consecutive-night dependence does not invalidate the coverage claim.

**Per-regime.** `normal` and `high_vol` are near-nominal at every anchor
(`normal` 0.691 / 0.853 / 0.953 / 0.992; `high_vol` 0.638 / 0.837 / 0.948 /
0.992). `earnings_night` (OOS $n \approx 60$ nights) realises 0.767 / 0.967 /
0.983 / 1.000 — a contract-favourable over-coverage on the small-$n$ earnings
cell (§B), the same one-sided asymmetry framed in §9.3: over-coverage is a
sharpness deficit, not a coverage failure, and tightens as the panel accumulates.

*Open item:* the overnight panel uses raw (unadjusted) opens, so ex-dividend
mornings enter as small systematic down-gaps; coverage holds at every $\tau$
without correction, and a dividend-adjusted rebuild is deferred to the §10
roadmap pending an upstream ex-dividend feed.

---

## B. Proposed §4.3 addendum + contribution — the `earnings_night` regime and calendar-conditioned coverage

The overnight cadence exposes a regime with no weekend analog and a property the
weekend panel cannot express. Unlike `high_vol` — a market state *inferred* from
trailing VIX — an earnings release is a **scheduled event with a publicly known
date and session**. This makes `earnings_night` the first regime the architecture
can condition on *a priori*: the band can widen deterministically ahead of a
known information event, before any volatility has been realised. We term this
**calendar-conditioned coverage**, and to our knowledge no production oracle
(Pyth, Chainlink Data Streams, RedStone, Kamino Scope) widens its feed for a
scheduled earnings release.

**Regime assignment.** An earnings event is assigned to the single overnight gap
it actually drives, using session timing (`bmo`/`amc`) from the upstream
earnings calendar (scryer `earnings.v2`): an after-close (`amc`) report dated
$t_0$ or a before-open (`bmo`) report dated $t_1$ fires inside the
close$(t_0)$→open$(t_1)$ gap. Session timing is complete for already-reported
earnings from 2015 onward — covering the entire OOS window. (A coarser
date-only flag that brackets both adjacent nights dilutes the regime with normal
nights and is strictly dominated; the single-gap assignment is what isolates the
tail below.)

**The earnings tail is large and distinct.** Standardised by the same
$\hat\sigma_s(t)$ the band uses, the realised overnight move on earnings nights
has $p_{99} \approx 9.7$ versus $\approx 2.0$ on all other nights, and mean
$|z| = 2.70$ versus $0.44$ — a roughly $\times 6$ fatter tail. The fitted
per-regime conformal quantiles reflect this directly: $q_{\text{earnings}}$ runs
≈ $8\times$ $q_{\text{normal}}$ across anchors (e.g. at $\tau = 0.95$, $15.8$ vs
$2.07$). The `earnings_night` band is wide because earnings nights genuinely are,
and §A shows it is calibrated, not merely wide.

**σ̂ de-contamination — earnings fatness is a regime effect, not a scale effect.**
Because an earnings residual can be $\sim 8\sigma$, letting it enter the
per-symbol EWMA scale $\hat\sigma_s(t)$ over-widens the subsequent ~`half_life`
*normal* nights and induces clustered post-earnings violations. We therefore
exclude earnings-night residuals from the $\hat\sigma_s$ estimation pool (every
night still receives a $\hat\sigma_s$ built from its non-earnings history),
assigning the earnings excess to the `earnings_night` quantile rather than the
scale. This separation is what lifts the overnight Christoffersen independence
$p$ at $\tau = 0.95$ from a rejecting $0.013$ to a passing $0.165$ (it
de-clusters the post-earnings violations) and collapses the OOS $c(\tau)$ bumps
to ≈1.0.

**Relation to Cong et al.** Cong, Landsman, Rabetti, Zhang and Zhao
[cong-tokenized-2025] document that off-hour price movements on tokenised
equities are *value-relevant-news-driven* and *anticipate* the underlying
close-to-open return. Earnings is the archetypal scheduled value-relevant-news
event, and the `earnings_night` tail measured here is the **underlying-side
confirmation** of that mechanism: the closed-market information set is revised
sharply and predictably on these nights, and a calibration-transparent band is
the constructive response — it widens, by a calendar-known amount, exactly where
Cong show information floods in. We are explicit about the boundary: this panel
is built on *underlying* equity opens and index-futures factors, not tokenised
prices, so it corroborates Cong's mechanism on the reference asset; it is not a
passthrough bake-off against tokenised feeds (that comparison remains the §10
forward-tape item).

---

## C. Threading checklist (edits to live sections, post-approval)

- **Abstract** — "5,996 weekend rows" → add the overnight panel; elevate the
  headline from a weekend result to an *off-hours* result (weekend + overnight,
  Kupiec & Christoffersen pass at all $\tau$ on both). Add `earnings_night` /
  calendar-conditioned coverage as a named contribution.
- **§1** — broaden the motivating frame: the closed-market valuation problem is
  every night, not only weekends; earnings nights are its sharpest, and
  schedulable, instance. Pull the Cong off-hours-news link up from §9 as forward
  motivation for calendar-conditioned coverage.
- **§4.3** — add the overnight regime set + `earnings_night` definition (§B
  paragraph 2) and the σ̂ de-contamination rule (§B paragraph 4); note the
  `gap_mode` parameterisation is a one-line change to the panel selector.
- **§6** — insert §A as new §6.8; renumber Summary → §6.9 and add an off-hours
  sentence to it.
- **§9.8 (scope)** — upgrade the "US-weekend only" scope statement to a
  *demonstrated* generalisation to overnight; move ex-dividend correction into
  the limitations list with the upstream-feed gate.
- **§10** — add: dividend-adjusted overnight rebuild; tokenised-passthrough
  bake-off against the Cong-implied baseline on earnings nights specifically.
- **Title** — consider "weekend" → "closed-market" / "off-hours".
