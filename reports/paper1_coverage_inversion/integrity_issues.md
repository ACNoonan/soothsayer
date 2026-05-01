# Paper 1 — integrity issue log

Discrete, individually-investigatable issues raised during the 2026-04-29
vetting pass against `docs/ROADMAP.md` "Gate 1: Paper 1 arXiv-hardening."
Each issue is scoped so it can be opened in a fresh session without
re-loading the whole paper; entries point to the specific section, line
range, and hooks to investigate.

Status legend: `[ ] open` / `[~] in-progress` / `[x] resolved` / `[d] dropped`.

When resolving, flip status and add a one-line `**Resolved YYYY-MM-DD:**`
note in place. Do not delete entries. Cross-link to
`reports/methodology_history.md` if the resolution changes a published
claim.

---

## Tier 1 — reviewer attack surface (resolve before arXiv)

### P1-01 — Underlier-vs-xStock target is the implicit calibration target
**Where:** §1.3 (headline claims paragraph), §6.1 (evaluation protocol),
§9.11 (existing on-chain disclosure).
**Concern:** The calibration target throughout the paper is the
underlier's Monday opening price (SPY, QQQ, …) on its primary venue. A
reader of §1.3 + §6.4 alone could conclude Soothsayer is calibrated
against on-chain xStock token prices; §9.11 acknowledges xStock TWAP is
unused as a forecaster but does not say the *target* is the underlier,
not the on-chain instrument. A protocol consuming the band against an
SPYx position is reading SPY's Monday open, not SPYx's weekend path.
Cong et al. (2025) already establishes the two are informationally
distinct in the closed-market window.
**Hooks:** §1.3 lines 41–52; §6.1 lines 5–14; §9.11 lines 85–89;
`docs/ROADMAP.md` line 34.
**Direction:** Likely a one-sentence anchor in §1.3 and a paragraph
expansion in §9.11. Decision: scope the paper as
"underlier-anchored band, xStock-anchored variant deferred to V2.1"
(cleanest), or attempt a partial xStock-anchored validation on the ~30
weekends the V5 tape carries today (probably underpowered).
**Status:** [ ] open

### P1-02 — Path-aware truth is not declared as a limitation
**Where:** §6 (computed against endpoint only), §9 (no current entry).
**Concern:** §6.4 measures realised coverage at the endpoint (Monday
09:30 ET open). Protocol risk is path-dependent — the worst executable
off-hours price along the path is what hits a borrower. Paper 3's plan
§12.5 already declares path-aware truth a precondition for that paper;
Paper 1 should disclose the corresponding gap rather than let a reviewer
find it.
**Hooks:** `reports/paper3_liquidation_policy/plan.md` §12.5;
`docs/v5-tape.md` for current Solana xStock executable-print history;
`docs/ROADMAP.md` line 34.
**Direction:** New §9.14 entry. Frame as "endpoint truth, not path
truth, with a one-table OOS extension reusing the same Kupiec /
Christoffersen battery as a future deliverable once on-chain print
history supports it." No methodology change required.
**Status:** [ ] open

### P1-03 — "Kamino flat ±300 bps benchmark" wording in §1.3
**Where:** §1.3 ¶5, line 47.
**Concern:** "…τ = 0.85, picked on protocol-EL grounds against a Kamino
flat ±300 bps benchmark…" violates the explicit ROADMAP rule:
*"Do not describe the legacy flat-±300bps benchmark as the literal
deployed Kamino xStocks incumbent anywhere in the Paper 1 narrative"*
(`docs/ROADMAP.md` line 22). The 2026-04-26 Kamino xStocks on-chain
snapshot retired the flat ±300bps story.
**Hooks:** `docs/ROADMAP.md` lines 15–22; §1.3 line 47.
**Direction:** Drop "Kamino" from this sentence; rephrase as "legacy
simplified flat-band benchmark." Cross-check P1-04 once resolved.
**Status:** [ ] open

### P1-04 — §6.4 simplified-Kamino disclaimer is buried in a parenthetical
**Where:** §6.4 "Other operating points" paragraph, line 65.
**Concern:** The disclaimer "the earlier simplified Kamino-style
flat-band benchmark" lives inside a parenthetical clause introducing
Paper 3. A reader skimming §6.4 will read "the current
protocol-deployment default" and silently bind that to actual Kamino
behaviour.
**Hooks:** §6.4 line 65; `docs/ROADMAP.md` line 31.
**Direction:** Promote the parenthetical to a leading sentence: "Paper
3 revisits this against the production xStocks reserve configuration;
the legacy ±300 bps comparator was a simplified benchmark and is not
deployed Kamino behaviour."
**Status:** [ ] open

### P1-05 — §6.7.2 Chainlink finding is too categorical for the sample
**Where:** §6.7.2 (Chainlink Data Streams subsection), lines 153–162.
**Concern:** Lead claim "the published band is degenerate — Chainlink
delivers a stale-hold point with zero published uncertainty" is
technically true *for the v11 weekend bid/ask on this sample* (87 obs /
11 weekends / Feb–Apr 2026 / 8 xStock tickers / pre-correction v10+v11
decoders) but reads as a categorical Chainlink-deployment claim. The
pre-decoder-correction caveat lives in §9.8 but is not inline.
**Hooks:** §6.7.2 lines 153–162; §9.8 line 61;
`reports/v1b_chainlink_comparison.md`;
`data/processed/v1_chainlink_vs_monday_open.parquet`.
**Direction:** Lead with sample bounds before conclusion; replace
"degenerate" with "structurally placeholder"; mirror §9.8's
pre-correction caveat inline.
**Status:** [ ] open

### P1-06 — v10 `tokenizedPrice` field exclusion is not stated where the comparison happens
**Where:** §6.7.2 (no current mention); referenced abstractly in §1.1
line 13 and §2.1 line 9.
**Concern:** The v10 schema's `tokenizedPrice` field updates
continuously across weekends, documented qualitatively as a
CEX-aggregated mark. Paper 1 does not measure it. A reader landing in
§6.7.2 will not know we excluded a continuously-updating field, and may
conclude the §6.7.2 finding applies to "Chainlink's tokenized-stock
product" categorically. This is the cleanest single reviewer attack on
§6.7.2.
**Hooks:** §1.1 line 13; §2.1 line 9; §6.7.2 lines 153–162; check
scryer for v10 `tokenizedPrice` capture before deciding.
**Direction:** Most likely a 2–3 sentence inline exclusion in §6.7.2
with a forward reference to §10. If scryer has the v10 `tokenizedPrice`
capture, consider a partial comparison instead. Resolve before P1-05.
**Status:** [ ] open

### P1-07 — v11 24/5 cadence finding is weekend-only; pre-market / overnight is open
**Where:** §6.7.2; §9.8; `docs/ROADMAP.md` line 122.
**Concern:** ROADMAP line 122 flags v11 24/5 cadence verification —
whether `mid`/`bid`/`ask` carry real values during pre-market /
overnight or are placeholder-derived as in `marketStatus = 5` — as
*open* as of the ROADMAP entry. Paper 1 §6.7.2 currently states the
placeholder finding without bounding it to `marketStatus = 5`. If v11
carries real values during 24/5 pre-market hours, the §6.7.2 finding
generalises from the worst-case window only.
**Hooks:** `docs/ROADMAP.md` line 122; `scripts/scan_chainlink_schemas.py`;
`docs/v5-tape.md` "Open empirical question" section.
**Direction:** If the cadence verification is done, fold the result
into §6.7.2. If still open, bound the §6.7.2 finding explicitly:
"verified for `marketStatus = 5` (weekend) only; pre-market and
overnight 24/5 cadence is currently open and will be resolved in
Phase 2."
**Status:** [ ] open

---

## Tier 2 — framing / overclaim drift (resolve before arXiv)

### P1-08 — "Missing infrastructure layer for responsible institutional-scale RWA onboarding"
**Where:** §1.0 ¶3, line 7.
**Concern:** Marketing voice in a research-paper introduction. The
block-explorer analogy is product-pitch framing.
**Direction:** Replace with a narrower research-framed claim, e.g.,
"We propose this primitive as a candidate calibration-transparency
layer for RWA classes with continuous off-hours information sets."
Drop the block-explorer analogy.
**Status:** [ ] open

### P1-09 — "Would benefit from" + "risk-reporting primitive"
**Where:** §1.0 ¶3, line 7 (same paragraph as P1-08).
**Concern:** "Would benefit from" is speculation. "Risk-reporting" is
product framing. Resolve alongside P1-08 if doing one editorial pass on
§1; otherwise standalone.
**Direction:** Replace "would benefit from" with "is structurally
compatible with"; drop the "risk-reporting" qualifier on "primitive."
**Status:** [ ] open

### P1-10 — Adverse-selection / liquidation concentration claim is uncited
**Where:** §1.0 ¶2.
**Concern:** "This gap… is also where the great majority of adverse
selection, undercollateralized liquidations, and protocol-level loss
events have historically concentrated." Strong empirical claim with no
citation — easy reviewer rebuttal.
**Hooks:** Cong et al. (2025) covers part of it; Daian et al. is
adversarial-ordering rather than closed-market-concentration. May need
a quantitative citation we do not currently have.
**Direction:** Either find a supporting citation or rephrase narrowly:
"this window is where the staleness gap is largest and where the
served oracle value contributes most directly to protocol
risk-budgeting decisions."
**Status:** [ ] open

### P1-11 — "Public-good infrastructure" + AUM market-sizing — §10.5
**Where:** §10.5, line 55 (BUIDL/OUSG "> $5B AUM as of submission");
line 57 ("public-good infrastructure").
**Concern:** Market-sizing pitch and product framing in a future-work
section of a methodology paper.
**Direction:** Drop the AUM figure entirely; replace "public-good
infrastructure" with the mechanical "the calibration-transparent
primitive applies by construction."
**Status:** [ ] open

### P1-12 — "Missing infrastructure layer" reprise in §9.10 and §10.5
**Where:** §9.10 line 83; §10.5 line 59.
**Concern:** Same phrasing as P1-08 reused twice. Repetition compounds
the marketing-voice impression.
**Direction:** Resolve P1-08 first, then propagate the chosen
replacement language to these two spots.
**Status:** [ ] open

### P1-13 — "§1.1 thesis confirmed empirically" — §6.8 summary
**Where:** §6.8, line 178.
**Concern:** "Both require consumer-side calibration with no audit
trail — the §1.1 thesis confirmed empirically." A 265-obs / 87-obs
subset cannot *confirm* a definitional thesis about three different
oracle products.
**Direction:** Soften to "consistent with §1.1's structural
observation on these subsets."
**Status:** [ ] open

### P1-14 — "The audit trail the calibration receipt provides for free" — §6.8
**Where:** §6.8, line 178.
**Concern:** The single most marketing-voiced line in §6. "For free"
is a sales register; the rest of §6.8 is in research register.
**Direction:** Replace with neutral framing, e.g., "Soothsayer's
served band is wider than either consumer-back-fit incumbent on this
subset; the comparison the paper claims is calibration-receipt
provenance, not bandwidth."
**Status:** [ ] open

### P1-15 — Caveat ordering in §6.7 lead
**Where:** §6.7, lines 133–135.
**Concern:** §6.7 ¶2 delivers the three caveats (sample-size CIs,
large-cap-only composition, consumer-supplied wrap multipliers) *after*
the comparison promise. Reader hits §6.7.1 / §6.7.2 numbers with
caveats buffered behind the initial framing.
**Direction:** Promote the caveats to the lead sentence of §6.7. Order:
caveats → what is reported → what is excluded (RedStone).
**Status:** [ ] open

### P1-16 — Pyth `k = 1.96` framing reads as a jab — §6.7.1
**Where:** §6.7.1, line 144 et seq.
**Concern:** "The textbook 95% Gaussian wrap (k = 1.96) returns 10.2%
realised — under-calibrated by ≈10× on this subset." Pyth never claims
σ is a Gaussian standard deviation; their docs describe σ as a
publisher-dispersion diagnostic. Calling the result "under-calibrated
by ≈10×" frames Pyth as failing a test it never opted into.
**Direction:** Attribute the 1.96 choice to the consumer, not to
Pyth's documentation: "k = 1.96, the value a consumer would pick if
reading σ as a Gaussian standard deviation, returns 10.2% realised on
this subset — consistent with Pyth's documentation that σ is a
publisher-dispersion diagnostic, not a probabilistic standard
deviation."
**Status:** [ ] open

---

## Tier 3 — cross-repo coherence (optional)

### P1-17 — README marketing voice vs paper voice
**Where:** `README.md` line 9.
**Concern:** "The promise of tokenized equities is real 24/7,
permissionless markets. The missing infrastructure is…" — repeats the
"missing infrastructure" framing in marketing voice. Appropriate for a
README, flagged only if you want product/paper voices to align after
P1-08 lands.
**Direction:** Defer until paper-side framing is settled. The README is
allowed to be louder than the paper; revisit only if the divergence
becomes jarring.
**Status:** [ ] open

---

Add new issues below this line as they surface. Keep numbering
contiguous (P1-18, P1-19, …).
