# Paper 1 v2 — Consolidated Adversarial Review (2026-07-18)

Four hostile reviewers over `build/paper_v2.md`, each verifying against repo
source (code, CSVs, oracle docs, figure PNGs): **statistics referee**,
**oracle-industry insider**, **protocol engineer**, **consistency linter**.
Findings deduplicated below; `[Nx]` = number of reviewers who independently
raised it (higher = stronger signal). Every item is CONFIRMED against source
unless marked SUSPECTED.

**Headline:** no fabricated numbers — everything reproduces. Damage is
(a) a handful of hard contradictions with the shipped code/docs, and
(b) headline framing that outruns what the panel can bear. Core contribution
(the auditable receipt) survives all four. Consensus disposition: **major
revisions**, none reversing the thesis.

---

## TIER 1 — BLOCKERS (hard contradictions / factual errors; fix before arXiv)

**B1. Algorithm 2 constructs a different band than the shipped code. [×2]**
Alg. 2 (App A) uses `L ← p̂·(1−q_eff)`, `q_eff = c·q_r·σ̂` — the retired M5
point-proportional formula. Main text / §3 / H2 / `oracle.py` use
`L = P̂ − c·q_r·σ̂·P_Fri`, `q_eff = c·q_r`. A reader following the paper's own
recipe fails byte parity when r_F ≠ 0. *Fix: rewrite Alg 2 to match serving
code; reserve q_eff for c·q_r everywhere.* (protocol #2, linter #1)

**B2. On-chain claims overstate what ships. [×2]**
§4.9 / A.8 say an Anchor program "serves the same [M6] bands" under a
"byte-for-byte, 180/180, three-implementations-agree" contract. Actual: 180/180
is Python↔Rust only; Anchor tests are scaffolded; on-chain is still the M5 path;
M6 enablement is gated on a future publisher release. The on-chain `PriceUpdate`
wire carries only 3 fields — **not** the receipt triple (c, q_r, σ̂) — so an
on-chain consumer cannot verify a band from the wire, contradicting the
"receipt re-derivable on every read" claim. *Fix: scope parity to Python↔Rust;
state on-chain = M5 today, M6 pending; scope the "receipt on every read" claim
to the off-chain read (or add the triple/sidecar-hash to the PDA).*
(protocol #3+#4, linter #4)

**B3. T1 grafts a Chainlink error onto Pyth.**
Stale-hold row attributes `OutsideMarketHours` (a Chainlink v8/Scope reject
path) to "Pyth core outside session." Pyth has no market-hours gate — outside
session its aggregate is suppressed on publisher dropout, status ≠ Trading.
*Fix: split the cell; OutsideMarketHours → Chainlink rep only; Pyth = "aggregate
suppressed / status ≠ Trading as publishers drop off."* (oracle #1)

**B4. T1 mislabels RedStone (self-contradiction).**
T1 row 6 calls RedStone Live "single 24/7 scalar from crypto-venue order books";
App F.4 correctly says it "blends institutional feeds with perpetual data."
RedStone sources institutional equity vendors for underlier tickers, no
crypto-venue books, no Solana on-chain equity feed. *Fix: reword T1 to match
F.4; RedStone is off-chain/underlier-only.* (oracle #3)

**B5. BoJ "1-in-10,000 under independence" is arithmetically wrong.**
Binom(10, 0.15) P(k=10) ≈ 5.8e-9 ≈ 1-in-1.7e8, not 1e-4. (H5's τ=0.95 figure is
correct.) Also "1-in-475" (§8) and "1-in-1,100" (H5) carry no inline τ tag, so
they read as contradictory. *Fix: recompute/relabel; tag "1-in-475 at τ=0.85
(k=10)" vs "1-in-1,100 at τ=0.95 (k=9)".* (linter #2)

**B6. earnings_night τ=0.85 is a significant miscalibration, framed as benign.**
Realises 0.967 (2 misses/60 vs 9 expected): Kupiec p≈0.003, a significant
over-coverage rejection. S2 and §6.5 frame all earnings anchors as benignly
"safe side." *Fix: flag the τ=0.85 earnings cell as a significant (over-wide)
rejection, not merely "above the promise."* (statistics #8)

**B7. ρ̂_cross wears one symbol for three different quantities. [×3]**
0.354 (§8/B.10, lag-1 cross-sectional AR) vs 0.41 (B.8/F.6, within-weekend
dependence) vs R̄ 0.36 (off-diagonal mean). *Fix: distinct symbols +
one defining sentence each.* (protocol #7, statistics implied, linter #10)

---

## TIER 2 — MAJORS (framing outruns evidence; each needs a decision — re-run vs caveat)

**M1. The 40/40 grid gives the deployed method a coverage knob the baselines never get.**
Deployed gets OOS-fit c(τ) evaluated in-sample at τ=0.95 (c(0.95)=1.079);
GARCH / const-buffer get train-fit only, no OOS coverage correction. Asymmetric
tuning on the flagship comparison. *Options: (a) re-run the grid with c held out
(LOSO/nested-holdout c) — most honest, may shift the headline; (b) give
baselines a symmetric post-hoc coverage scalar; (c) caveat "grid is c-in-sample
at τ=0.95" in place.* (statistics #1)

**M2. "Statistically tied" width (378 vs 371 bps) is asserted, never tested.**
No paired test/CI; widened GARCH-t never re-run through Kupiec at matched width;
tie-target inconsistent across artefacts (378/385.3/370.6). *Options: (a) compute
a paired block-bootstrap CI on the matched-coverage width delta (a script run);
(b) drop "statistically tied," say "comparable."* (statistics #2)

**M3. k*=3 / p99≈5 / "0/24 stability" rest on ~8 tail events.**
P(k≥3)=4.62% CI [1.73, 7.51] straddles both binomial 1.15% and values >5;
"0/24 rejections" is a power statement (18/24 cells flagged low-power). *Options:
(a) carry the [1.73,7.51] CI into the §8 headline + label k*=3 "point estimate
under limited power"; (b) leave as-is (appendix already discloses).*
(statistics #3)

**M4. Tokenized head-to-head (−45%/−46%) conflates architecture with a ~100× calibration-history edge.**
Deployed calibrated on the frozen 12-yr artefact; the tokenized baseline gets an
expanding-window empirical quantile, 4-weekend warm-up, ≤19 weekends/symbol
(perp tape starts 2025-12). *Options: (a) re-run handicapping the deployed band
to the same post-2025-12 sample; (b) state explicitly that the comparison
conflates architecture with calibration-history length.* (statistics #4)

**M5. Endpoint-vs-path caveat is absent from the abstract.**
Headline 0.9497 is endpoint coverage; a continuously-exposed lending consumer
(the named use case) sees path coverage 0.788 at τ=0.95 (residual 9-15pp after
confounds). *Decision: pull the endpoint-vs-path distinction into the
abstract/contributions, or keep it in §8/B.14?* (statistics #11)

**M6. "All ten pass Kupiec" masks two ~2.5-3pp under-coverers.**
AAPL 0.9249, GLD 0.9306 in LOSO; per-symbol MDE ~4pp so "pass" is a power
statement for the low symbols. Also "0.9497 ± 0.0128" is a cross-symbol SD (range
0.925–0.965), formatted as a tight uncertainty band. *Fix: add the per-symbol
LOSO spread + MDE caveat to §6.1; label ±0.0128 "cross-symbol SD."*
(statistics #7, #12)

**M7. Overnight block-bootstrap resamples the wrong dependence.**
It orders within-symbol-then-chrono and does 1-D block bootstrap, destroying the
within-night cross-sectional co-breach (ρ_cross=0.354) §8 identifies as the real
dependence. *Options: (a) re-run bootstrapping by night/weekend block (whole
cross-sections); (b) caveat that the CI cannot see cross-sectional dependence.*
(statistics #5)

**M8. Pyth publisher-vs-aggregate "95%" wall rests on one un-cross-checked 2022 blog.**
The categorical thesis leans on "Pyth's ~95% addresses individual publishers,
not the aggregate," sourced only to a blog gloss, not corroborated in canonical
pyth_regular.md. *Fix: quote the blog's exact wording; if it's aggregate-framed,
soften to "Pyth frames conf probabilistically but publishes no verifiable
realised-coverage claim."* (oracle #2, SUSPECTED)

---

## TIER 3 — MINORS (mechanical; batch-fixable, mostly one right answer)

- **Stale cross-refs [×2]:** §4.7 "§6.8" → §6.4 (×2); §6.5 + H4 caption "§4.3.1"
  → §4.7 (×2); §1.3 "Appendix A" for Kamino snapshot → App F (or create the
  exhibit). (protocol #6, linter #12)
- **Count reconciliations [×3]:** 5,996 vs 5,916 evaluable; 228 vs 229 earnings
  nights; 117 vs 118 Kraken cells; F.3 "26 reports" vs 20 mapped. One canonical
  count per object. (statistics #15, oracle #4, linter #7/#16)
- **Christoffersen p order-artifactual [×2]:** 0.603↔0.720↔0.989 same fit, row
  order unspecified. Report order-robust (min over orderings) or lean on
  DQ/permutation; stop citing exact p. (protocol #14, statistics #13)
- **Numeric typos:** D.6 "0.052-0.058" → 0.035-0.046; C.1/D.2.2 "29-31%" →
  31-38%; NVDA "variance-undefined boundary (2.50)" → "optimizer lower bound
  ν̂=2.50, adjacent to ν≤2"; C.3 "2.23" → 2.12 (or label sim-fitted);
  §6.5 "1.78× entire band width" → "1.8× baseline half-width". (linter #5,#6,#14,#15,#18)
- **§9 vs F.10 width-cost sign:** §9 "at a disclosed width cost" vs F.10
  "tightens −11.6%." Reconcile. (linter #9)
- **Caption-vs-body:** H5 caption "fitted joint model's p99≈5" → "empirical p99≈5
  (t-copula ≈6)". (linter #3)
- **"8×" referent drift:** fitted quantile ratio is 4.85× at the p99 anchor, not
  8×; H4 ties 8× to realized move; H1b to quantile ratio. State the τ / separate
  the referents. (linter #11)
- **Units drift:** H3 subtitle "1,730 weekends" → "symbol-weekends (173
  weekends)"; B.1 "80 weekends" → "80 rows". (linter #13)
- **r_F classification [×2]:** §3.1 + Fig 1 caption call it pre-publish; §5.3 says
  post-publish. Mark observable-during-window; define the r_F measurement window
  precisely in §5.4. (protocol #5, linter #17)
- **Codenames / TODO [×2]:** define M5/M6/LWC at first use; strip working-doc
  notes ("SPINE.md §3", "parallel session", future-dated provenance) and the A.3
  "must be refreshed at submission" TODO. (protocol #11, linter #19)
- **Mixed citation syntax [×2]:** [cong-tokenized-2025, p.20], [@romano-cqr-2019,
  Fig.4] → \citep. (protocol #12, linter #20)
- **Jargon-before-gloss:** POF, CAViaR, NMS, HLP, "z"-score used before defined.
  (protocol #12)
- **§2 spelling seam:** American (organized/standardized) in §2 vs British
  elsewhere. (protocol #13)
- **Sim DGPs A-D near-tautological:** hard-code the scale heterogeneity σ̂
  removes; only DGP-E stresses the mechanism (and fails, 59.5%). State A-D isolate
  the scale effect. (statistics #9)
- **Forward-tape "10/10 at τ=0.95" vacuous at N=11:** HOOD, MSTR at 18.2%
  (opposite the pooled over-coverage). Report them; drop "directionally
  consistent." (statistics #10)
- **τ=0.99 per-symbol pass-counts ~powerless** (expected 1.73 viol/symbol);
  down-weight in headline tallies. (statistics #14)
- **40/40 grid: no MHT on 120 evals;** note 40/40 is over-conservative-consistent,
  not neutral. (statistics #6)
- **SEDA:** move USA500 out of "tracks the wrapped token" (it's a composite
  index); acknowledge its ~95%-gap-closure marketing claim. (oracle #5)
- **Blue Ocean "24/5"** → "overnight (Sun–Thu 20:00–04:00 ET)". (oracle #6)
