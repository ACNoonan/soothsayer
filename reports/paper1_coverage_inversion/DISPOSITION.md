# Paper 1 — Reverse-Outline Disposition Map

**Status:** step-2 output of the structural rewrite (2026-07-16). Maps every
paragraph/table/figure/equation of the current draft to a slot in the SPINE.md
skeleton, an appendix, CUT, or MH (methodology_history.md only).

**How to read:** `Lines` are Read-tool line ranges prefixed by source shorthand
(00: abstract, 01: intro, econ: economic_motivation_draft, 02: related work,
ps: problem_statement, 04/05/06/07/08/09/10/11/12: numbered sections,
cs: case_study_high_vol). Appendix letters: **App-A** reproducibility,
**App-B** full validation battery, **App-C** simulation study, **App-D**
ablation detail + σ̂ ladder, **App-E** serving layer, **App-F** oracle
comparator / extended diagnostics.

**§0 Synthesis (orchestrator):** written after all slices landed — see end of file.

---

## Slice A — 00_abstract.md + 01_introduction.md + economic_motivation_draft.md

| Lines | Content (≤10 words) | Disposition | Keep-words | Rewrite directive |
|---|---|---|---|---|
| 00:3 | Full 330-word abstract paragraph | Abs | 200 | Rewrite to SPINE formula: one-sentence hook + K2 + three strongest K3 numbers (LOSO 0.9497±0.0128, 40/40 Kupiec vs GARCH-t 31/40, overnight generalization) + K4 in one clause each. Drop 38/40 Christoffersen / 39/40 DQ detail, anchor arithmetic, implementation list (one clause max). Keep "receipt". |
| 01:3 | Composability promise; 0.10% weekend trade density; 102 liquidations | §1/stakes + §1/blunt-response | 180 | Split: trust-precondition framing opens §1 (~60w); trade-density + zero-off-hours-liquidations facts move to blunt-instrument paragraph, "consistent with" framing verbatim. |
| 01:5 | 32% wall-clock fact; Cong duality; JELLYJELLY/Volcano incidents | §1/stakes + §1/preview | 150 | Keep 6.5h/32% as H1 anchor sentence. Cong λ=0.903 dual-signal ~60w. JELLYJELLY/Volcano only with mechanism attributed to cited post-mortems. |
| 01:7 | Coverage-inversion preview: τ in, band out, receipt | §1/preview | 60 | Nearly as-is; K2 preview sentence. Merge with receipt-tuple sentence from 01:36. |
| 01:9 | Market-size figures; extended-hours proposals; generalisation map | §1/stakes | 150 | Keep $29B RWA + BUIDL-as-collateral + Ondo/xStocks volume. CUT $963M/2,878% growth and $16T/10%-GDP projection (AUM-pitch, P1-11 pattern). Keep extended-hours "reshapes, doesn't eliminate" (~70w). |
| 01:11 | Overnight windows; earnings night; calendar-conditioned coverage | §1/preview | 70 | Two sentences: overnight calibrates with gap-selector change only; earnings' public dating enables calendar-conditioned coverage. |
| 01:13–15 | §1.1 heading + no-incumbent-receipt claim | §1.2/T1 | 40 | Becomes §1.2 "What the window serves" lead claim (absence claim, guardrail-safe). |
| 01:17–24 | Six-archetype table: mechanics per representative | §1.2/T1 | 200 | T1's "mechanics" column. Merge with §6.7 measured-findings + sample-bounds columns (Slice E supplies). Lab-report register. |
| 01:26 | Categorical-not-bandwidth-comparative; Pyth per-publisher | §1.2/T1 | 50 | Keep the disarming sentence; Pyth per-publisher note → T1 footnote. |
| 01:28 | Cong TSLAx wedge stats; structural persistence | §1.2/T1 | 90 | Wedge stats (71%/15% >1%, 12% >5% vs ±500bps clamp) → two sentences under T1. Persistence one clause; rest CUT. |
| 01:30 | Cong mean-vs-quantile distinction | §1.2/T1 | 70 | Keep closing argument (conditional-mean ≠ conditional-quantile; no width, no regime signal). Quintile detail → App-F. Soften "SLA requires" → "would need". |
| 01:32–34 | §1.2 heading; τ anchors, interpolation, wire format | CUT | 0 | §3 owns the contract spec. Verify §3 retains anchor set + interpolated-not-validated disclosure before deleting. |
| 01:36 | Auditability + receipt properties; SR 11-7 lineage | §1/preview | 40 | One sentence: receipt tuple re-derivable from public data. Lineage cut here (owned by §2/§3). |
| 01:38 | Binding consumer set | §1/stakes | 100 | One sentence per consumer category. Keep "over-engineering for perp settlement" non-claim clause. CFB documentation-bar judgment: restate factually or cut. |
| 01:42 | Panel spec | CUT | 30 | §5 owns. Only "639 weekends × 10 symbols, 2014–2026; 22,624 overnight windows" survives inline. |
| 01:44–48 | Three headline claim bullets | §1/contrib | 80 | One number per claim; corroborating sub-detail cut (owned by §6/§8). Add Kupiec/DQ glosses at first use. |
| 01:50–56 | Five contributions C1–C5 | §1/contrib | 120 | Recast as K1–K4 (C5 demoted to K3 support clause). Update cross-refs. |
| 01:58–60 | Non-claim + roadmap | §1/contrib | 55 | Keep non-claim; rewrite roadmap against new skeleton. |
| econ:15–34 | Stakes passage; integrity-vs-calibration; institutional discount | §1/stakes | 60 | Unique keeps: integrity-vs-calibrated-statement distinction (~30w, sharpest framing) + peg-breaks-when-closed Cong anchor. "Rational institutional response…" recast "consistent with" or drop. "Left the experimental phase" CUT (marketing). |
| econ:36–46 | Extended hours narrow but don't close | §1/stakes | 40 | Merge into 01:9. CUT "binding unlock… primitive this paper supplies" (pitch register). |
| econ:50–66 | Sourced-data table + citation notes | CUT | 0 | Retain in reports/active/ as pre-submission citation-verification checklist. |

**Budget:** Abs 200/200; §1 ~1,585 of 2,200 (~615 reserved for T1 findings from Slice E, gap-tail prose, H1 anchor, K-framing glue).

**Gaps (A):** (1) measured gap-tail distribution — nowhere in these files, import from 05/06 or write vs H1; (2) T1 measured-findings column bridge paragraph = new writing; (3) Kamino conservative-reserve-config facts (2026-04-26 snapshot) not in these files; (4) xStocks $186M AUM≪volume contrast needs a prose sentence; (5) H1 anchor paragraph; (6) Kupiec/DQ glosses; (7) K1–K4 reframing prose.

**Voice flags (A):** "stakes are no longer speculative" (adjectival); $16T/2,878% (P1-11 pattern — do not reintroduce); JELLYJELLY $12M causal claim (attribute to post-mortems); CFB documentation-bar judgment (K1 guardrail); econ "rational institutional response" (P1-10); econ "binding unlock" (P1-08/09); abstract "no incumbent oracle provides" → bound to "no surveyed incumbent surface".

---

## Slice B — 02_related_work.md + problem_statement.md

| Lines | Content (≤10 words) | Disposition | Keep-words | Rewrite directive |
|---|---|---|---|---|
| 02:3 | Three literatures, never combined | §2 opening | 50 | State empty-intersection punchline up front; fold MRM into para (b). |
| 02:5–7 | Deployed oracle landscape catalog | §2 para (c) | 150 | One clause per venue family; schema-version minutiae → App-F. |
| 02:9 | No venue publishes calibration claim; wire evidence | §2 para (c) | 120 | Keep claim + why comparison undefined; per-venue field evidence → App-F. |
| 02:11 | Academic integrity literature | §2 para (c) | 60 | Keep adversarial-vs-statistical contrast; BIS/Flash Boys one cite each. |
| 02:13 | Integrity vs calibration orthogonality; Sunday example | §2 punchline | 70 | Keep intact — this IS the empty-intersection argument. |
| 02:15–17 | Cross-venue discovery: Hasbrouck, futures lead | CUT (cites → §4) | 0 | Hasbrouck/Stoll-Whaley/Gonzalo-Granger cites move inline to §4 base-forecaster definition. |
| 02:19 | Weekend as regime: French, Barclay-Hendershott | CUT (facts → §1) | 0 | French + 3–4× after-hours-spread facts forward to §1/K1 stakes owner. |
| 02:21 | Cong et al. wedge, four findings | §2 para (c) tail | 80 | One positioning sentence: conditional-quantile complement is absent — that is this paper. Numeric detail → §1.2/T1 owner. |
| 02:23–25 | VaR backtesting: Kupiec, Christoffersen, Basel, PIT | §2 para (b) | 120 | Keep with voice-rule-4 glosses; compress Diebold/Berkowitz to cite list; expand PIT/LR on first use. |
| 02:27 | Gneiting sharpness-subject-to-calibration | §2 para (a) | 60 | Keep as organizing objective; delete predecessor-chronology clause → MH. |
| 02:29 | Mondrian split-conformal, CQR, non-exchangeability | §2 para (a) | 140 | Keep Vovk/Mondrian + CQR-as-upgrade + Barber/Xu-Xie one clause each; internal-comparator parenthetical → App-D. |
| 02:31–33 | Institutional MRM: SR 11-7, Basel | §2 para (b) close | 40 | Fold into VaR paragraph final sentence. |
| ps:3–13 | Setup, observed variables, regime labeler, base forecaster | §3.1 | 325 | Keep shape; update §6.x cross-refs. |
| ps:15–17 | Classical oracle problem | §3.2 | 80 | Keep; fix stale "§1.1 archetypes" → §1.2/T1. |
| ps:19–41 | Inversion: D, surface, q_served, PricePoint (equations) | §3.3 | 200 | Keep all four equations intact. Add H2 figure reference at PricePoint block. Reconcile tuple with K2 receipt list (see gap B5). |
| ps:43–49 | P1 auditability + P2 statement | §3.4 | 140 | Keep intact. |
| ps:51 | P2 caveat block: holdout axes, Kupiec MDE | §3.4 + App-B | 40 | One sentence ("finite-sample deviations measured, tested (§6), disclosed as buffer"). MDE/power discussion → App-B. |
| ps:53 | P3 efficiency, band formula, σ̂ ladder | §3.4 | 120 | Keep criterion + dominance claim; formula once with §4 forward-ref; ladder → App-D cross-ref. |
| ps:55–64 | Non-goals 1–6 | §3.5 | 250 | Keep all six (K-claim guardrails), 1–2 sentences each. |
| ps:66–75 | Evaluation questions Q1–Q4 | CUT | 0 | Superseded by contributions list + claim-ordered §6. |

**Budget:** §2 ~890/900; §3 ~1,155/1,200.

**Gaps (B):** (1) explicit "the intersection is empty" thesis sentence = new; (2) DQ citation + gloss missing from §2 entirely (Engle–Manganelli never cited) — §2 para (b) must add; (3) H2 hook at PricePoint block = new; (4) Hasbrouck cites need §4 owner to accept; (5) **receipt-field mismatch**: SPINE K2 says (τ, c(τ), q_r(τ), σ̂_s, r), draft tuple is (P̂, L, U, q_served, r, f) — §3 must reconcile or H2 contradicts the formalism; (6) Cong 71%/15% wedge facts must actually land in §1.2/T1 or they vanish.

**Voice flags (B):** 02:17–19 unglossed information-share jargon (moot, CUT); 02:25 PIT/LR unglossed; 02:27 predecessor chronology; 02:29 internal-history parenthetical; 02:7 venue catalog over-detailed for its claim; ps:17 stale cross-ref.

---

## Slice C — 04_methodology.md + 05_data_and_regimes.md

| Lines | Content (≤10 words) | Disposition | Keep-words | Rewrite directive |
|---|---|---|---|---|
| 04:1–5 | Intro; implementation paths; four-ingredient overview | §4 opener | 130 | One-sentence opener + recipe roadmap. Parity sentences merge with 08-sourced deployment paragraphs — do not double-count. |
| 04:7 | fig1 pipeline diagram + caption | §4 (keep fig1) | 50 | Trim caption ~40%; keep receipt/P1 clause. |
| 04:9–13 | §4.1 point estimator equation | §4.1 | 85 | Keep equation + factor examples; "residual input, not the product". |
| 04:15 (end) | Eight-variant ladder survived pruning | MH | 0 | Chronology. |
| 04:17–23 | §4.2 σ̂ EWMA equation, warm-up | §4.2 | 120 | Keep equation, HL=8, strict pre-t window, warm-up. Constants → App-A. |
| 04:25 | HL=8 ladder selection | App-D | 25 | One-sentence pointer: "selected under pre-registered three-gate criterion (App-D)". |
| 04:27–35 | §4.3 conformity score; Mondrian; scalars; calibration set | §4.3 | 180 | Keep score equation, regime set, anchor grid, scalar count, split + per-bin N. Rejected-rung sentence → MH; JSON path → App-A. |
| 04:37 | Why σ̂ standardization works; bimodality | §4.3 | 80 | Mechanism claim; cite §6/simulation (rule 2). HOOD 3× SPY keeps. |
| 04:39 | Within-bin exchangeability test | App-B | 20 | One clause + pointer. |
| 04:41–43 | §4.3.1 gap_mode selector; overnight re-derivation | §4.3.1 | 55 | Keep "one-line change" claim (K3). Definition dedupes to §5.5; consequence here. |
| 04:45 | earnings_night; calendar-conditioned; 8× quantile | §4.3.1 | 110 | Keep — K3 calendar-conditioned claim. "No production oracle widens" must stay a factual absence statement. |
| 04:47 | σ̂ de-contamination mechanism | §4.3.1 | 80 | Keep mechanism; Christoffersen result → §6/App-B, cite only. |
| 04:49 | fig11 earnings event study | §6 (H4) | 0 | Figure leaves §4; caption + mechanism prose hand to §6 owner. |
| 04:51–57 | §4.4 c(τ) schedule + fit | §4.4 | 85 | Two sentences; §9.3 provenance pointer → new §8. |
| 04:59–61 | §4.5 δ(τ) ≡ 0 | §4 one sentence; App-D | 25 | "δ≡0 under walk-forward selection (App-D); retained for receipt-schema compatibility." |
| 04:63–73 | §4.6 five-step serving lookup | §4.6 | 210 | Keep five steps tight; off-anchor caveat → one sentence + §8 pointer. Trim first if §4 overruns. |
| 04:75–77 | §4.7 PricePoint receipt; re-derivation | §4.7 (H2 anchor) | 100 | Keep — H2's textual anchor. Compress field list (formal in §3); keep floating-point-precision verification sentence. |
| 04:79–85 | Python/Rust parity; repro commands | App-E / App-A | 0 | Superseded by 08 absorption; commands verbatim → App-A. |
| 04:87 | <100 KB verification footprint | §4.7 | 35 | Keep — auditability number serves K2/H2. |
| 05:1–3 | Intro + rebuild scripts | §5 opener | 20 | One sentence; scripts → App-A. |
| 05:5–9 | §5.1 universe; NYSE opens as target | §5.1 | 85 | Symbol list + rationale one sentence; keep target-scoping sentence. |
| 05:11–15 | §5.2 schema + panel counts | §5.2 | 115 | Field list one sentence (full → App-A); keep headline counts + span. |
| 05:17 | fig0 weekend-returns + caption | §1 (H1) | 0 | Hand to §1 owner; three named stress weekends survive in H1. |
| 05:19–21 | §5.2.1 overnight panel; earnings timing; ex-div | §5.2 | 85 | Keep counts + one clause each; 241-morning detail → App-B. |
| 05:23–25 | §5.3 pre-publish features | §5.3 | 40 | Compress; "pre-publish property matters for K2". |
| 05:27–39 | §5.4 switchboard + MSTR pivot | §5.4 | 80 | Keep table compact + one MSTR sentence. V1b β-regression history → App-D. |
| 05:41–51 | §5.5 regime cascade + overnight counts | §5.5 | 100 | Keep cascade + shares + overnight counts; definition lives here, consequence in §4.3.1. |
| 05:53–55 | realized_bucket; tested-and-dropped refinements | App-B / MH | 0 | Diagnostic labeler → App-B; dropped refinements → MH. |
| 05:57–68 | §5.6 split + quantiles-fixed disclosure | §5.6 | 100 | Keep split date, table, quantiles-fixed disclosure (K3 honesty); HOOD-pooling dup CUT. |
| 05:70–83 | §5.7 scryer provenance; runtime/commands | §5.7 / App-A | 25 | One provenance sentence; rest verbatim → App-A. |

**Budget:** §4 ~1,390 + ~110 (from 08) = 1,500/1,500 (at ceiling; trim 04:63–73 first). §5 ~650 + ~50 forward-tape para = 700/700.

**Gaps (C):** (1) **forward-tape harness absent from 05** — §5 needs ~50 words from 06/`reports/m6_forward_tape_11weekends.md` (frozen content-addressed artefact, weekly append, no refit); (2) H2 partially describable — 04 covers band re-derivation but not consumer-facing framing or *surface* re-derivation as a verification flow — one new bridging sentence; (3) serving-layer double-count risk with 08 absorption (merge, not concatenate); (4) overnight regime definition duplicated 04↔05 — convention: definition+counts §5.5, consequence §4.3.1; (5) fig11/H4 relocation: §6 owner needs 04:45/47 mechanism prose.

**Voice flags (C):** 04:15, 04:35, 05:39, 05:55 chronology (→MH/App-D); 04:45 "no production oracle widens" is guardrail-safe as absence claim — keep exactly that shape; Christoffersen/Berkowitz unglossed; "sidecar" must not become a receipt synonym.

---

## Slice D — 06_results.md §6.1–§6.3

| Lines | Content (≤10 words) | Disposition | Keep-words | Rewrite directive |
|---|---|---|---|---|
| 3 | §6 intro: LOSO headline + deferrals | CUT | 0 | Superseded by new §6 lead in K3 claim order. |
| 5–7 | §6.1 protocol: panel, split, test conventions | §6 capsule + App-B | 80 | Keep ≤3 sentences: N, split, Kupiec/Christoffersen glosses. Warm-up, four-mode enumeration, point-estimator stats → App-B. §5 owns panel construction; §6 owns eval split + glosses. |
| 9–20 | §6.2 in-sample machinery check | App-B | 0 | Whole subsection; one-line pointer from §6. |
| 22–24 | §6.3 lead: two-axes holdout frame | §6 (K3 lead) | 60 | "Held out on two orthogonal axes — symbol (LOSO) and time (nested holdout)" = the K3 lead sentence. |
| 26–33 | OOS per-regime table + commentary | App-B | 25 | Inline keep: pooled 0.950 / 370.6 bps at τ=0.95. |
| 35–44 | §6.3.1 conditional-coverage table + commentary | App-B | 80 | Inline keep: realised 0.9503, Kupiec p=0.956, Christoffersen p=0.603, passes every anchor. One "failure mode is §8's subject" sentence. |
| 46–57 | §6.3.2 tertile decomposition | App-B | 0 | Move intact; §8 gets one cross-ref clause. |
| 59 | fig2 calibration curves | §6 (H3) | 60 | Merge with fig5 into single H3 panel (cross-slice; orchestrator assigns). |
| 61–63 | §6.3.3 stability lead: temporal 0.9504 + LOSO | §6 (K3 headline) + App-B | 90 | Lead §6 with this. Keep temporal 0.9504 (p=0.947, 10/10) + LOSO 0.9497±0.0128 + TUNE-anchor range. BoJ c=1.175 mechanism → App-B. |
| 65 | LOSO CV paragraph | §6 (K3 lead) | 80 | Procedure one sentence, result one, uniform-band one. |
| 67–76 | §6.3.3.1 nested holdout + mode table + sensitivity | §6 + App-B | 90 | Split definition + 0.9504 + "c matches at three decimals — not fit-on-evaluate sensitive". Tables/detail → App-B. |
| 78–96 | Lower-τ over-coverage; split-date; calendar sub-period | App-B | 35 | Inline clauses only: "stable across four split anchors"; "holds 2023–2026-YTD; 3/16 rejections all toward over-coverage". |
| 98 | Welfare-optimal τ scope sentence | CUT | 0 | Redundant with §3 non-goals. |
| 100–110 | §6.3.4 k_w setup + joint-tail table | §8 (K4 lead) + App-B | 110 | Keep k_w definition + baseline list + inline: P(k_w≥3)=4.62% vs binomial 1.15%, variance ratio 2.34, max k_w=9. Copula fitting detail → App-B. |
| 112–114 | fig10 + overdispersion paragraph | §8 (H5) | 110 | Keep fig10 (H5): k*=3 mark, BoJ annotation, 10⁻⁴-vs-10⁻³ contrast. Keep 2.3× overdispersion bracket; Wasserstein/L-sweep → App-B. |
| 116–118 | k* thresholds + operational guidance | §8 (K4 headline+close) | 100 | Keep k*=3 (4.62%), 0/24 stability, reserve-to-99th-pct≈5, and the "no incumbent publishes this distribution" K4 moat line. Other-τ detail → App-B. |
| 120–143 | §6.3.5 BoJ weekend: setup, table, fig9, macro, mechanism | §8 (worst-case, one paragraph) + App-B | 170 | Two-sentence setup; table+fig9 → App-B; keep MSTR-663-vs-SPY-85 contrast, common-mode mechanism, real-time k_w=10 vs fitted k*=5, 1-in-475-vs-1-in-10,000. Strike "worked as designed". |
| 145–151 | §6.3.6 DQ + Berkowitz + localisation | §8 one sentence + App-B | 85 | Keep: "pooled DQ (gloss) rejects — per-anchor, not full-distribution, calibrated" + ρ_cross=0.354 vs ρ_time=−0.032 localisation. Spec detail → App-B. |

**Budget (D):** §6 slice ~540 + H3 caption 60 (inside ~1,000 share). §8 slice ~530 + H5 caption 60 — **nearly fills §8's 900 shared with 09**; trim to ~430–450 at rewrite (merge 114+116; cut macro clause; compress 143) so limitations get ~400.

**Gaps (D):** (1) H3 merge is cross-slice (fig2+fig5) — orchestrator assigns; (2) §6/§5 seam convention (§5 owns construction, §6 owns split+glosses); (3) new §6 lead must set up four-beat order (LOSO/holdout → grid → overnight → earnings); (4) §8's positive claim "publishing k_w is enabled by the receipt design" is asserted, never argued — needs one bridging sentence from §3/K2; (5) confirm four kept numbers suffice for self-supporting H5 caption.

**Voice flags (D):** Kupiec/Christoffersen unglossed at first use; "working as designed"/"exactly as designed" (2×, strip); "contract-favourable sharpness deficit" unglossed → "over-wide, not under-covering"; "independence strawman" 3× → keep once; "not a freak" colloquial; "CAViaR Table 1 block 1" insider shorthand must not appear in §8.

---

## Slice E — 06_results.md §6.4–§6.9

Numbering note: in the current file **§6.7 is the simulation study** (→ App-C by
content). The **oracle comparator** (Pyth wrap 10.2%, Chainlink v11 synthetic
markers) is **not present anywhere in 06_results.md** — see Gaps E1.

| Lines | Content (≤10 words) | Disposition | Keep-words | Rewrite directive |
|---|---|---|---|---|
| 153–155 | §6.4 intro: 10/10 Kupiec headline | §6 (master-grid lede) | 40 | One lede sentence before the grid; PIT-variance detail → App-B. |
| 157 | fig4 per-symbol calibration | §6 (fig S1) | 60 | Keep supporting figure; trim caption cross-ref chatter. |
| 159–180 | §6.4.1 per-symbol Kupiec/Berkowitz table + power caveat | App-B | 30 | §6 cites "10/10, rates 3.5–6.9%" inline; TLT/TSLA Berkowitz → §8 K4 slot; power caveat → App-B with table-footnote pointer. Strike "one of the strongest… claims" self-praise. |
| 182–204 | §6.4.2 master-grid setup + 40-cell table + NVDA footnote | §6 (THE table) | 310 | Keep whole table — the spine's one §6 table; 40/40 vs GARCH-t 31/40 is the K3 headline. Gloss the three tests at the grid if §6.3.6's glosses got appendixed. Compress NVDA dagger footnote ~50%. |
| 206 | Leads every baseline; pooled-DQ localises cross-sectionally | §6 + §8 | 110 | First two sentences → §6; DQ/ordering mechanism → §8 (merge with Slice D's §6.3.6 rows). |
| 208–225 | §6.4.3 GARCH baselines: setup, tables, width tie, proper scores | §6 clauses + App-B | 70 | Inline: GARCH-t 0.928 realised vs claimed 0.95 (p<0.001) vs deployed 0.950 (p=0.956); "t-innovations fix the wrong end" clause; optional Winkler −12.9%. **Preserve the matched-coverage width tie (≈378 vs 370.6 bps) — honesty-critical concession, do not cut.** Drop "known straw-man" phrasing. |
| 227 | fig5 Pareto | §6 (merge into H3) | 60 | Merge fig2+fig5 into one H3 panel. Caption's "incumbents do not emit a band, comparison not well-defined" sentence = the model guardrail language — preserve verbatim as T1's attribution template. |
| 229–250 | §6.4.4 per-asset-class; §6.5 path coverage + fig6 + guidance | App-B | 20 | Explicit spine instructions. Keep sample bounds in appendix headers; neutralize "sharpens the contract" advocacy; §8 gets one endpoint-not-path clause. |
| 252–260 | §6.6 forward-tape harness + status + sibling script | §5 (1–2 sentences) + App-A | 45 | Harness sentences → §5; hash/ops detail → App-A. **Line 258 N=5 is STALE → 11 weekends.** Keep "never used to re-select" disclosure. |
| 262–286 | §6.7 simulation study (five DGPs, sweeps, figure) | App-C | 25 | Move intact; §7 may cite pass-rate pair (29–31% → 98.6–99.9%) as K3 support. DGP-E location-shift blind spot: one §8 sentence ("σ̂ absorbs mean jumps as variance; CUSUM closes it — App-C"). Corroborative-not-predictive chronology stays in App-C as integrity disclosure, never in main text. |
| 288–292 | §6.8 motivation + one-change rebuild | §6 | 110 | Keep "property of the method, not the weekend" framing + "one change — the gap selector" + 22,624 rows. Regime re-derivation mechanics → §5/App-B. |
| 294–305 | Overnight pooled table + headline + bootstrap | §6 + App-B | 65 | Inline: "passes every anchor, ≈3.8× larger panel, c(τ)≈1.0" + one bootstrap clause; table → App-B. |
| 307 | Per-regime; earnings_night; ex-div | §6 (earnings slot, feeds H4) + App-B | 60 | earnings_night → §6 earnings beat; **must import 7.1× widening / 1.78× baseline / 8× tail numbers from fig11's caption (in 04!)**. Ex-div detail → App-B. Verify numbers against refreshed earnings.v2 artefact. |
| 309 | fig8 overnight calibration | §6 (fig S2) | 55 | Keep; caption already carries the claim. |
| 311–313 | §6.9 summary recap | CUT | 0 | Spine-directed; all numbers verified to have upstream homes. |

**Budget (E):** §6 ~750–850 incl. table + three captions; §5 ~45–60; §8 ~90–120; §1.2/T1 **0 — comparator content absent from this file**.

**Gaps (E):** (1) **T1's measured findings must be imported from outside the paper dir**: `reports/v1b_pyth_comparison.md` (Gaussian-wrap 10.2%) + `docs/sources/oracles/chainlink_v11.md` §3 (synthetic markers) — and the source framing "under-calibrated by ≈10×" is exactly what P1-16 struck; §1 owner must rewrite to consumer-attribution. Full methodology → App-F from same sources. (2) fig11/H4 + its numbers live in 04 — single-placement coordination. (3) forward-tape N stale. (4) earnings_night numbers may predate earnings.v2 re-wiring — verify. (5) DQ/Kupiec gloss location if §6.3.6 appendixed.

**Voice flags (E):** "one of the strongest… claims" (applause); "known straw-man" (editorial); "sharpens the contract rather than weakening it" (advocacy on a limitation); §6.7 chronology disclosure OK in App-C only; fig5-caption guardrail sentence is the house style — replicate.

---

## Slice F — 07_ablation.md

Framing note: the file's own trio (lines 5–7) is stratification / σ̂ / **c(τ)**;
the SPINE trio is stratification / σ̂ / **selection procedure**. Rewrite must
promote §7.4 to component 3 and demote §7.3 (c(τ)) wholesale to App-D.

| Lines | Content (≤10 words) | Disposition | Keep-words | Rewrite directive |
|---|---|---|---|---|
| 1–7 | Intro + three-component bullets | §7 opening + slots 1–2 leads | 160 | Claims-first rewrite; swap component 3 to selection procedure; c(τ) bullet → App-D. Keep 2/10→10/10 headline. |
| 9 | Roadmap paragraph | CUT | 0 | Furniture. |
| 11 | Block-bootstrap CI methodology | §7 methods note | 25 | One sentence (1000 resamples, paired by (symbol, fri_ts)); paths → App-D. |
| 13–34 | 7.1 constant-buffer: definition, tables, undercoverage | §7 slot 1 + App-D | 150 | One definition sentence; keep −14.2/−12.0/−5.4pp + Kupiec rejection + non-stationarity mechanism (2 sentences); strike "catastrophically". Tables/equation → App-D. |
| 36–51 | 7.1.2–7.1.3 matched-width + per-regime decomposition | §7 slot 1 + App-D | 70 | Keep −5.7%/−6.3% with CIs + one high_vol +52% clause. Tables → App-D. |
| 53–72 | 7.2 unweighted Mondrian: definition, table, mechanism, width tax | §7 slot 2 + App-D | 125 | One definition sentence; keep compensating-bias mechanism + +4.5% width tax with CI [+1.05, +30.73]. Table → App-D. |
| 74–87 | 7.2.2 isolation + simulation cross-check | App-D | 25 | One salvage sentence (LOSO std 5.9× tighter, Berkowitz range 250×→5.2×). Simulation cross-check cites App-C/D. |
| 89 | fig7b + caption | App-D | 0 | Per SPINE. |
| 91–93 | 7.2.3 walk-forward δ-shift | App-D + MH | 0 | Finding → App-D; chronology → MH. |
| 95–103 | 7.3 c(τ) schedule analysis | App-D | 0 | Whole subsection. |
| 105–122 | 7.4 σ̂ selection: gates, BH correction, Gate-3 table, forward-tape | §7 slot 3 + App-D | 190 | Keep: pre-registered three gates over five-variant family; gates 1–2 don't discriminate after BH FDR (gloss BH); Gate 3 −3.83% [−6.15, −1.88] at τ=0.95; forward-tape re-validation clause — **refresh N=5 → 11 weekends** (`reports/m6_forward_tape_11weekends_variants.md`), keep below-power caveat. Tables → App-D. |
| 124–154 | 7.4.1–7.4.3 quartile-cutoff, split-anchor, regime-index ablations | App-D | 0 | Supporting robustness battery. |
| 156–171 | 7.5 width-tax redistribution | App-D | 20 | One clause into slot 2 (+17.8% equities / −48.8% defensive explains pooled +4.5%). |
| 173 | §10 pointer | CUT | 0 | Duplicated by §9. |
| 175–255 | 7.6 tokenized-tracking baseline (Cong λ=0.903): construction, bake-off, −45% hw, per-symbol, power caveat, Jupiter cross-check | App-D — **but see promotion flag** | 0 | ORCHESTRATOR FLAG: 7.6.3's −45% half-width / −46% Winkler at matched coverage vs the tokenized-tracking baseline is arguably stronger than the GARCH-t comparison and answers the "lazy oracle" objection — consider promoting one row + the 7-of-9 honest concession into §6 master-grid discussion. Strike "naive bull case… rejects that hope", "This is the right read". Gloss Winkler wherever it lands. |

**Budget (F):** §7 ~610/700 (~90 slack for transitions/glosses).

**Gaps (F):** (1) slot-3 lead (selection procedure as component) = genuine new writing; (2) §7.6 homeless in spine — promotion decision needed; (3) stale forward-tape N (5 → 11).

**Voice flags (F):** "catastrophically undercovers"; walk-forward chronology; "Five σ̂ variants were compared" passive-chronology; "Status at submission: N=5" stale; "naive bull case"; "This is the right read"; unglossed Winkler/Berkowitz/Christoffersen/BH-FDR/DGP/Hasbrouck-passthrough.

---

## Slice G — 08_serving_layer.md + 09_limitations.md + case_study_high_vol_20240802.md

| Lines | Content (≤10 words) | Disposition | Keep-words | Rewrite directive |
|---|---|---|---|---|
| 08:3 | Four-component stack intro | §4 (deployed para) | 40 | One claim-first sentence: "deployed — Python reference, Rust serving, Anchor on-chain." |
| 08:5–9 | Three audiences; Python canonical spec | §4 survivor + App-E | 70 | Keep "Python `oracle.py` is the executable spec; Rust serves under parity contract"; strip "implemented first, then ported" narration. |
| 08:13–45 | Crate table; Anchor invariants; wire format | App-E | 0 | Verbatim (incl. code block + Pyth-2021 post-mortem cite). |
| 08:47–53 | Parity harness 180/180 | §4 one sentence + App-E | 25 | §4 keeps "byte-for-byte Python↔Rust parity, 180/180"; mechanics → App-E. |
| 08:55–88 | Repro commands; integrator path; worked example; k*; receipt | App-E | 0 | Merge command block into App-A to avoid two listings. 08:86 k* duplicates §8 content — appendix copy cross-refs, never restates. Optional lift: "choosing τ sets the per-name breach budget to 1−τ". |
| 09:3 | Limitations intro | §8 opening frame | 30 | One sentence naming the residuals in K4 order. |
| 09:7–9 | Shock tertile 87.8%; calm over-coverage compensation | §8 (shock bound) + App-F | 105 | Keep 87.8% + "misses more often, doesn't widen" mechanism, n=632 inline; "compensating tertile biases; over-coverage side is a sharpness deficit" clause. |
| 09:11 | Circuit breaker would have fired on BoJ | §8 (merge) | 15 | MERGE into Slice D's BoJ paragraph — do not restate. |
| 09:15–17 | P2 stationarity; sub-period grid | §8 bound + App-B | 65 | Keep assumption statement + one "holds across four calendar sub-periods" clause. |
| 09:19 | Three unpre-emptable violations | §8 | 40 | One sentence listing breaks/labeler drift/switchboard; upgrade pointer → §9. |
| 09:23 | c(τ) provenance | App-B | 0 | No claim bound. Stale "N≥13 forward weekends" gate — nearly met at N=11; provenance disclosure may be upgradable. |
| 09:25–27 | Asymmetric failure modes; receipt field | §8 one sentence + App-F/E | 30 | Keep thesis: "documented failure modes are asymmetric toward over-coverage; under-coverage is the alarm side." |
| 09:31–39 | Per-anchor NOT full-distribution; cluster topology; ρ numbers; Berkowitz localisation | §8 (core K4 lead) + App-F | 135 | §8 headline; gloss Berkowitz + DQ on first use. Keep 2.34×, ν≈6, "σ̂ operates within-symbol, structurally unable to reach this residual" (justifies "disclosed, not fixed"). Details → App-F. |
| 09:41–43 | Consumer guidance; per-anchor SLA ≠ portfolio solvency | CUT / §8 | 60 | 09:41 restates — cut. 09:43's "k_w is the bridge" claim keeps; Slice D owns the k numbers, this cites. |
| 09:47–53 | Forward tape N=5 (STALE); CUSUM bank | App-B / App-F | 15 | Refresh N. Optional §8 sentence: "a deployed CUSUM drift monitor fired on both stress weekends" (strengthens K4 monitoring story). |
| 09:57–59 | No numerical incumbent comparator; endpoint vs path +16.1pp | §8 | 95 | Keep both: guardrail-compliant boundary statement; endpoint-contract bound + τ=0.99 closure. Robustness details → App-B. |
| 09:61–65 | MEV unmeasured; no optimal-policy benchmark | App-F / §8 clause | 20 | One clause: "k* is reserve guidance, not an optimal policy — that requires a cost model out of scope." |
| 09:69–75 | Temporal/region/asset-class scope; admission floor | §8 clause / App-F / App-C | 20 | Only earnings_night small-n caveat survives in §8; asset-class requirement → §3 non-goals (coordinate); N≥200 floor → App-C. |
| 09:81–84 | Non-claims: manipulation, latency, σ̂ optimality; xStock TWAP | §3 non-goals / App-E / App-D / §8 | 110 | Manipulation orthogonality placed ONCE (§3 non-goals preferred). Keep underlier-vs-xStock bound in §8: "we predict the underlier; tokenized-side conditional-mean baseline exists (Cong λ=0.903) and deployed band dominates best perp-backed baseline on Winkler at every τ." |
| 09:86–88 | Off-anchor τ interpolated, not audited | §8 | 40 | Bounds K2's "consumer picks τ": four audited anchors; off-anchor interpolated + receipt-detectable. |
| 09:92–96 | Cong epistemic status; Kamino Open/AllUpdates undecoded | App-F → **T1 footnote** | 0 | **09:96 must surface as a T1 caption bound** (per-reserve mode governance-mutable, undecoded) — flag to §1 owner. |
| 09:98 | "Disclosures, not retractions" closer | CUT | 0 | Defensive rhetoric; K4 stance carries it. |
| cs:1–66 | BoJ case study (v1-era) | App-B — **STALE** | 0 | Generated 2026-05-03 against pre-M5 v1 surface (F0_stale + log-log VIX); numbers do not describe deployed M6 LWC. Enter App-B only re-run on frozen M6 artefact OR labeled "historical v1 surface". §8's BoJ paragraph sources from 06 §6.3.5, NOT from this doc. Strip "thoughtful Kamino risk committee" editorializing; note comparators are hypothetical consumer configs, not incumbent products. |

**Budget (G):** §4 ~135 (fits "two paragraphs" allowance); §8 ~480–530 of the 900 shared — over when combined with Slice D (see §0); cut order here: CUSUM clause, sub-period clause, sharpness clause (−55).

**Gaps (G):** (1) §8 BoJ paragraph cannot source from the case study (stale surface); (2) k*/reserve triple-stated across 09:11/41/43 + 08:86 — one owner (Slice D's §6.3.4), all else cites; (3) forward-tape N stale; (4) manipulation + asset-class boundary items → §3 non-goals, place once; (5) Kamino Open/AllUpdates indeterminacy must reach T1's caption; (6) Berkowitz gloss missing from spine's pre-written glosses — suggest "test that the full predictive distribution, not just the band edge, is calibrated."

**Voice flags (G):** cs "thoughtful Kamino risk committee" (rules 3+6); cs stale-stack description; 08 process narration; 09:23 "substantially contracted" draft-history; Berkowitz/DQ unglossed; 09:98 defensive rhetoric; normalize "calibration-receipt provenance"/"first-class receipt" → "receipt".

---

## Slice H — 10_future_work.md + 11_conclusion.md + 12_appendix_reproducibility.md

| Lines | Content (≤10 words) | Disposition | Keep-words | Rewrite directive |
|---|---|---|---|---|
| 10:1–3 | Extensions intro + ROADMAP list | §9 lead-in | 20 | One clause; drop six-item parenthetical. |
| 10:5–7 | §10.1 full-distribution conformal + cluster partial-out | §9 (conformalized-upgrade slot) + App-F | 80 | Keep shape only (DQ residual → Romano CQR-style correction → cluster partial-out closes it); numbers (ρ̂ 0.477→0.077, DQ p=0.912, −11.6% hw) → App-F. Frame as "closing §8's disclosed failure mode" (K4 link). |
| 10:9–11 | §10.2 path-fitted score, AMM, MEV variant | §9 one clause + App-F / MH | 30 | AMM consumers need path-fitted score, gated on V5 tape N≥300. Strip "library-grade". MEV/Jito → MH. |
| 10:13–15 | §10.3 earnings-night bake-off | §9 one clause + App-F | 25 | Tie to K3; cut "(previously listed here, is now applied)" chronology. |
| 10:17–19 | §10.4 forward-tape rebuild + live window | §9 (protocol-integration slot) + App-A | 60 | Keep live devnet→mainnet window vs real consumer protocol; rebuild mechanics → App-A/MH. |
| 10:21 | Out-of-scope list | §9 close | 15 | One scope sentence. |
| 11:1–3 | Conclusion recap | §9 open | 60 | Interface (K2) + architecture (K3) in claim order; cite §7/App-C, don't re-walk. |
| 11:5 | Honest scope: ties SPY/TSLA, wins long-tail | §9 | 45 | Keep "value concentrates where incumbents are weakest" framing. |
| 11:7 | Bottom line: one number, one boundary | §9 close | 110 | Strongest paragraph — keep structure nearly intact; fix stale cross-refs; final sentence stays the paper's last line. |
| 12:5–129 | A.1 algorithm boxes; A.2 scalar tables | App-A | — | Stays. §4 cites Algorithms 1–2 as "the recipe" — no pseudocode duplication. **FLAG: "sixteen scalars total" is a §4 candidate** (K3's simplicity claim) — "sixteen scalars (Table A.2)" + high_vol 6.46σ shape one sentence. |
| 12:131–135 | A.3 data availability + repo/tag/license | §5 (condensed) + App-A | 50 | Two-sentence provenance version in §5; full stays App-A. Refresh snapshot date at submission. |
| 12:137–228 | A.3–A.6 code layout, compute, pipeline, figure provenance | App-A | — | Stays. **A.6 figure-provenance table must be rebuilt after H1–H5/S1–S2 re-plan.** |
| 12:230–246 | A.7 determinism; A.8 Rust/on-chain 180/180 parity | App-A | — | Stays; "deployed; Python/Rust/Anchor, 180/180 parity" is one of §4's two allowed serving sentences (cross-ref, not duplicate). |
| 12:248–251 | A.9 within-bin exchangeability test | App-B | — | Validation-battery material, not reproducibility. |

**Budget (H):** §9 ≈ 395–445 vs 400 — at ceiling. Cut order if over: earnings clause (25) → path clause (30) → compress recap to 40. Protect 11:7 bottom-line + upgrade/integration slots.

**Gaps (H):** (1) "the primitive stands independent of this architecture" never stated — one new sentence; (2) protocol-integration mechanics thin — one sentence bridging k*=3 reserve guidance to a Kamino-shaped integration sketch; (3) conformalized upgrade never framed as closing K4's disclosed failure mode — add link; (4) stale internal numbering pervasive.

**Voice flags (H):** P1-11 AUM sizing CONFIRMED ABSENT (strike held); "public-good infrastructure" absent; "library-grade" self-praise; "previously listed here, is now applied" chronology; "operational scaffolding"/"production realism" gloss; 11:7 rhetorical close earns its place but must keep citation anchors.

---

## §0 Synthesis

### 0.1 Budget rollup (main text)

| § | Budget | Mapped keep-words | Status |
|---|---|---|---|
| Abs | 200 | 200 | ✔ at ceiling |
| §1 | 2,200 | ~1,585 + T1 imports (~400–500) | ✔ tight; T1 imports come from OUTSIDE the draft (see 0.3.1) |
| §2 | 900 | ~890 | ✔ |
| §3 | 1,200 | ~1,155 (+ non-goal arrivals from 09:73/81) | ✔ tight |
| §4 | 1,500 | ~1,390 + ~135 (08 absorption) = ~1,525 | ⚠ trim 04:63–73 (serving lookup) first |
| §5 | 700 | ~650 + ~50 (forward-tape) | ✔ at ceiling |
| §6 | 2,000 | ~540 (D) + ~800 (E) + captions ≈ 1,450–1,550 | ✔ headroom for the earnings beat + H4 relocation |
| §7 | 700 | ~610 | ✔ |
| §8 | 900 | ~530 (D) + ~505 (G) + ~105 (E) ≈ **1,140** | ✘ over by ~240. Cut order: D trims to ~440 (merge overdispersion+k* paras, drop macro clause, compress 1-in-475 to final sentence); G drops CUSUM/sub-period/sharpness clauses (−55); E's DQ mechanism merges into D's DQ sentence rather than adding one. |
| §9 | 400 | ~395–445 | ⚠ at ceiling; cut order: earnings clause → path clause → compress recap |
| Total | ~10,000 | ≈ 9,800–10,100 | ✔ viable |

### 0.2 Cross-slice coordination rules (binding for step-3 section writers)

1. **k_w / k* numbers have ONE owner:** Slice D's §6.3.4 rows (in new §8). 09:11, 09:41–43, 08:86 cite, never restate.
2. **Overnight regime split:** definition + counts in §5.5; architectural consequence (calendar-conditioning, σ̂ de-contamination) in §4.3.1.
3. **§5 owns panel construction; §6 owns eval split + test glosses.**
4. **H3 = fig2 + fig5 merged into one panel.** Owner: §6 writer (D's slice provides fig2 prose, E's provides fig5/Pareto prose). New composite figure to build.
5. **fig11 (H4) relocates §4 → §6** with its 7.1×/1.78×/8× numbers; §4.3.1 keeps the mechanism prose, §6 keeps the result + figure. Single placement.
6. **Glosses:** Kupiec ("binomial test of violation rate") and Christoffersen ("independence-of-violations test") at §6's first use; DQ ("regression test that violations are unpredictable") at §8's first use or the master grid if needed earlier; Berkowitz ("test that the full predictive distribution, not just the band edge, is calibrated") at §8. PIT/LR expanded in §2. BH-FDR appositive in §7. Winkler glossed wherever it first lands.
7. **Cite migrations:** Hasbrouck/Stoll-Whaley/Gonzalo-Granger → §4 (base-forecaster definition); French + Barclay-Hendershott after-hours-spread facts → §1 stakes; Cong wedge numbers (71%/15%, 12% >5% vs clamp) → §1.2/T1; Engle–Manganelli DQ cite ADDED to §2 (currently missing entirely).
8. **Non-goals placed once:** oracle-manipulation orthogonality + asset-class scope requirement → §3.5; §8 does not restate.
9. **Receipt-field reconciliation:** §3's PricePoint tuple (P̂, L, U, q_served, r, f) vs SPINE K2's (τ, c(τ), q_r(τ), σ̂_s, r) must be unified BEFORE H2 is drawn — H2 must match the formalism exactly.
10. **T1 attribution template:** fig5's caption sentence ("incumbent surfaces do not emit a calibrated coverage band, so a coverage-vs-sharpness comparison is not well-defined") is the house guardrail language — replicate its shape in T1 and §1.2.
11. **"Receipt" is the only product noun** — normalize "sidecar" (distinct object, fine), "first-class receipt", "calibration-receipt provenance".

### 0.3 Master gaps = step-3 new-writing worklist

**Imports from outside the draft (not moves):**
1. **T1 measured-findings column** ← `reports/v1b_pyth_comparison.md` + `docs/sources/oracles/chainlink_v11.md` §3. The Pyth source's own framing ("under-calibrated by ≈10×") is P1-16's struck pattern — rewrite to consumer-attribution on import. Full comparator methodology → App-F from the same sources.
2. **Forward-tape harness paragraph for §5** ← 06:252–254 + `reports/m6_forward_tape_11weekends.md`. Refresh N=5 → 11 everywhere (06:258, 07:122, 09:47); the "N≥13" provenance gate is nearly met.
3. **Kamino reserve-config facts (2026-04-26 snapshot)** for §1's blunt-instrument paragraph.

**Genuinely new prose (no source anywhere):**
4. Measured gap-tail stats for §1 (weekend vs overnight vs earnings-night distribution) — compute from panel; anchors H1.
5. §1.2 "What the window serves" bridge paragraph.
6. xStocks $186M-AUM-vs->$10B-volume sentence (figures exist only in econ's table).
7. "The intersection is empty" thesis sentence (§2).
8. H2 caption bridging band re-derivation → surface re-derivation as a verification flow.
9. §6 lead paragraph setting the four-beat claim order.
10. §8 bridging sentence: publishing k_w is *enabled by* the receipt design (currently asserted, never argued).
11. "The primitive stands independent of this architecture" (§9).
12. k*=3 → Kamino-shaped integration sketch sentence (§9).
13. §7 slot-3 lead (selection procedure as the third load-bearing component).
14. K1–K4 contributions prose replacing C1–C5.

**New figures:** H1 (blind-window composite, upgrade fig0), H2 (anatomy of a read), H3 (fig2+fig5 merge). App-A's figure-provenance table rebuilt after.

**Verification before writing:** earnings_night per-regime numbers vs refreshed earnings.v2 artefact (E gap 4); §3 retains τ-anchor set + interpolation disclosure before 01:34 is deleted.

### 0.4 Decisions needing Adam

1. **Promote §7.6 tokenized-tracking head-to-head into §6?** The −45% half-width / −46% Winkler at matched coverage vs the perp-backed tracking baseline is arguably stronger than the GARCH-t comparison and directly answers "why not just track the 24/7 token price?" Costs ~100 words of §6 headroom (available) + the 7-of-9 honest concession.
2. **BoJ case study:** re-run on the frozen M6 artefact (a script run) or enter App-B labeled "historical v1 surface"?

### 0.5 Stale-data fixes (mechanical, do before step 3)

- ~~Forward-tape N: 5 → 11 weekends~~ **DONE 2026-07-16** — 06:258, 07:122, 09:47,
  and the §6.9 summary line updated with the 11-weekend numbers (pooled Kupiec
  passes all four anchors, per-symbol 10/10 at τ=0.95).
- ~~earnings_night overnight numbers vs post-earnings.v2 artefact~~ **DONE
  2026-07-16, premise inverted:** earnings_night values were already current
  (post-fix state = benign over-coverage on n=60 — keep as drafted, do not
  "fix"). Actual staleness was the pooled table + normal/high_vol rows
  (pre-ex-div-adjustment) + TRAIN typo (16,094→16,093) + bootstrap CIs — all
  corrected in 06:294–307. §6 rewrite cites
  `reports/active/overnight_calibration_firstread.md` (HEAD, 2026-06-25) as the
  single §6.8 source. Story improved: Kupiec p at τ=0.95 is 0.710 (was 0.509).
- ~~BoJ case study re-run on frozen M6 artefact~~ **DONE 2026-07-16** —
  `case_study_boj_m6.md` (self-checking runner `scripts/build_case_study_boj_m6.py`,
  sanity-gated against §6.3.5's k_w = 10/9/5). App-B uses the M6 version; the
  original is historical, cited nowhere. Honest-read sentence survives: no method
  attains nominal coverage at τ ≤ 0.95 on this weekend (M6 best cell: 1/10 at
  τ=0.95); at τ=0.99 M6 ties the best comparator (5/10) incl. MSTR's −2,737 bps
  move, with conditional rather than flat widths. Caveat carried: comparator
  half-widths are v1-era pre-2023-trained values, kept for comparability.
- ~~Gap-tail stats for §1/H1~~ **DONE 2026-07-16** — `stats_gap_tails.md`
  (headline: 13.8% of weekends had ≥1 symbol move >500 bps; worklist item 0.3.4 closed).
- App-A snapshot date + figure-provenance table: refresh at rewrite.

### 0.6 Decisions log

- 2026-07-16: K1 reframed to taxonomy + measurement + adoption asymmetry (SPINE
  updated; §1→2,400, §6→1,800, T1 gains evidence-class column).
- 2026-07-16: §7.6 tokenized-tracking head-to-head PROMOTED to §6 (one paragraph,
  constructed-proxy framing, numbers stay out of master grid).
- 2026-07-16: BoJ case study → re-run on M6 artefact, historical-label fallback.
- 2026-07-17: Adam approved Abs/§1/§3/§6/§8 as written (incl. the new §8
  receipt-enables-k_w argument). §1 opening rewritten: numbers labeled by measure
  (stock/commitment/flow); extended-hours moved to §1.1 as a permanence argument.
- 2026-07-18: Full figure redesign APPROVED (Adam sign-off): all main-text
  figures rebuilt to the one-question-per-figure standard with in-figure claim
  titles + lean captions — H1 split into H1a/H1b; H3 → promised-vs-delivered;
  S1 → per-symbol promise audit; S2 → overnight/earnings promise audit (no
  connector bars, small-n defusal on the 100% cell); H4 → absolute-bps
  event-time band (7.2× ratio-of-medians; prose uses ≈7×); H5 → linear-count
  joint tail (τ=0.95-correct BoJ odds: 1-in-1,100 fitted / 1-in-10¹¹
  independent). Old figs remain appendix exhibits. LaTeX: caption package +
  short running title; T1 → 4-col table + full-width findings prose.
- 2026-07-17: §9 retitled "Conclusion", future-work register removed per Adam
  ("this paper stands alone"): extensions → present-tense consumer capability +
  App-F characterisation ("not deployed, nothing depends on it") + one
  out-of-scope sentence; "named as the target of the next generation" →
  "disclosed on every read".
