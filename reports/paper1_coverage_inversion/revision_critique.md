# Paper 1 — Critical revision pass (2026-06-10)

Adversarial read of the full arXiv version (build of 2026-05-25, N=5 forward-tape refresh applied 2026-06-08). Benchmark for narrative/figure quality: Cong et al. (exemplars/Tokenized-Stocks-Cong). Items ranked by severity. Each has a checkbox; strike when done.

---

## A. Defects a hostile reviewer can quote against the paper

### A1. fig5 contradicts the paper's own methodological stance — BLOCKER
- [ ] The §6.4.3 caption for `fig5_pareto.pdf` states: *"The figure is restricted to methods that emit a calibrated coverage band — incumbent oracle surfaces (Pyth, Chainlink Data Streams, RedStone, Kamino Scope) do not, so a coverage-vs-sharpness comparison against them is not well-defined."* §9.6 repeats this: *"we therefore do not report one."* **The actual figure plots `Pyth ±k·conf (n=265)` and `Chainlink Streams mid ±k% (n=87)` as data series.** A referee quoting the figure against §9.6 wins instantly.
- Root cause: captions rewritten 2026-05-25; figures last rendered 2026-05-09; `scripts/build_paper1_figures.py` still emits the old design (its own docstring says fig5 = "M6 / Soothsayer-v0 / GARCH / Pyth / Chainlink").
- Fix: edit `fig5_pareto` in the builder to drop Pyth/Chainlink/Soothsayer-v0; keep M6 + GARCH-t (the only methods the text compares numerically). Regenerate. Or, if the incumbent points are wanted, rewrite caption + §9.6 + §1.1 — but the categorical-not-numerical stance is load-bearing for the §2 framing, so dropping the points is the right direction.

### A2. fig2 does not match its caption — BLOCKER
- [ ] Caption (§6.3.2): *"GARCH(1,1)-t markers (vermilion squares) at the four served anchors… visibly under-cover."* **The figure contains no GARCH-t series.** It shows: constant-buffer (orange), `Soothsayer-v0 (legacy hybrid)` (yellow), M5 (green), M6 (blue). Same root cause as A1.
- Additional problems with the figure as built:
  - `Soothsayer-v0 (legacy hybrid)` is never defined anywhere in the manuscript text — internal repo lore leaking into the headline calibration figure.
  - Legend renders a literal escape: `F0\_stale` (backslash visible).
  - M5 and M6 are visually indistinguishable on the pooled curve — *by construction* (both pool to nominal; the difference is per-symbol). The headline figure therefore shows the deployed method tied with its ablated comparator. Underselling and confusing.
- Fix: regenerate to match caption (M6 + GARCH-t markers + CB), drop v0 and M5 from this figure (per-symbol contrast lives in fig7b where it belongs).

### A3. fig1 pipeline diagram: stale scalar count + receipt typo
- [ ] Footer says **"16 deployment scalars"**; verify against §A.2 / text convention (12 q_r + 4 c, with δ≡0 retained as 4 more in the artefact JSON — STATUS.md counts 20). Pick one convention, state it identically in fig1, §4.4–4.5, §A.2.
- [ ] The PricePoint receipt line in the figure shows `τ` twice (`…as_of, τ, δ(τ)=0, τ, p̂_t…`) — looks like a duplicated field; should match §4.7's field list (`target_coverage`, `claimed_coverage_served`, …). Rendering also generally weak for the only architecture figure (see C2).

### A4. §12 reproducibility appendix: figure inventory stale
- [ ] Says *"produces all 6 paper figures"* and tables only Fig 1–6. The paper now uses 10 (fig0, fig7b, fig8, simulation_summary missing from the table). Refresh the table + count.

### A5. Internal codenames inside figure artwork
- [ ] fig7b title: *"§7.2 OOS per-symbol ablation…"* — a section cross-reference baked into the artwork (breaks if sections renumber; AFT carve renumbers).
- [ ] simulation_summary title: *"Phase 3 simulation study"* — internal phase naming meaningless to a reader.
- [ ] M5/M6/LWC appear in legends of figs 2, 5, 6, 7b, sim. Captions define M5/M6 locally in fig7b only. Either define the M-series naming once in §4 footnote, or relabel rows/legends descriptively ("unweighted Mondrian", "deployed (σ̂-standardised)"). Recommend the latter; the text already uses descriptive names everywhere.
- [ ] fig6 title/legend also says "M6".

### A6. "Open-sourced" claim — verify before submission
- [ ] Abstract: *"Reference implementation open-sourced (Python + Rust + Anchor; §8)."* Confirm the repo is actually public at submission time (or soften to "reference implementation provided / available on request / to be released").

---

## B. Narrative — where it falls short of the Cong bar

The Cong intro pattern that works: **(1)** plain-language hook with a concrete tension, **(2)** 4 numbered research questions, **(3)** findings summarised under bold mini-headers, one paragraph each, plain sentences, **(4)** literature positioning last. The reader knows the entire paper by page 5 without meeting a single Greek letter.

### B1. The intro has two beginnings — merge them
- [ ] §1 para 1 (the May-25 economic-importance insert: trade-density 0.10%, 102 liquidations, circular fallback) and §1 para 2 ("Tokenised equities and other RWAs trade 24/7. Their underlying venues do not…") are *both* written as openings. Para 2 restarts the motivation from scratch. Merge into one arc: promise → trust precondition → off-hours vacuum (density + liquidation evidence) → dual nature of the off-hour process → stakes. Cut ~30%.

### B2. "Coverage inversion" — the title concept — is not defined until §3.3
- [ ] §1.2 is headed "Coverage as a first-class API parameter" and describes the design, but the *inversion* one-liner (conventional oracle: point + band with coverage implicit and unauditable → inverted oracle: coverage τ is the input, the band is the output, the receipt is the proof) never appears crisply in §1. A reader of title → abstract → §1 has to reconstruct the metaphor. Add the two-sentence definition in §1's first or second paragraph and make §1.2's heading "Inverting the oracle interface" or similar so title, abstract, §1, §3 use one name.

### B3. Abstract is hostile to its audience
- [ ] One ~350-word paragraph, with the raw tuple $(s, \rho(\mathcal{F}_t), \hat\sigma_s(t), \tau)$ and "locally-weighted Mondrian split-conformal" in sentence 3. q-fin.RM and AFT referees skim abstracts; the math tuple belongs in §4. Rewrite as 4 moves: problem (2 sentences, no notation) → primitive in plain words → evidence (LOSO headline + 40-cell grid + overnight generalisation + earnings calendar-conditioning) → honest residual (DQ pooled). Target ≤250 words.
- [ ] The earnings/calendar-conditioned coverage sentence is the most *product-differentiated* claim in the paper ("band widens deterministically ahead of a scheduled event — which no incumbent oracle does") and it's buried mid-abstract. Consider it the closer.

### B4. Contributions list is one breathless sentence
- [ ] §1.3's C1–C5 sentence is ~150 words with nested parentheticals. Convert to the Cong device: five bold mini-headers, one short paragraph each. Same content, half the cognitive cost. (The "Three headline empirical claims" bullets just above it are already close to the right shape — the C1–C5 sentence below them is redundant with them; consider merging the two lists into one.)

### B5. The same stat block appears four times
- [ ] LOSO 0.9497±0.0128 / 40-40-38-39 grid / 370.6 bps / k*=3 / BoJ k_w=10 appears nearly verbatim in: abstract, §1.3, §6.9 summary, §11 conclusion (and partially §6.3.1, §6.3.3). Each repetition dulls it. Assign roles: abstract = headline only; §1.3 = claims with §-pointers; §6.9 = full technical recap (keep); §11 = *interpretation* (what the result means for oracle design), not a re-listing. Cut the stat dump from §11 and let its honest-scope paragraph (SPY/TSLA tie) carry the conclusion — that paragraph is the best writing in the paper.
- [ ] Same disease lower down: the k*/reserve-guidance material is explained in §6.3.4, §6.3.5, §9.1, §9.4, §8.7, §11. State the mechanism once (§6.3.4), reference everywhere else.

### B6. Sentence-level register
- [ ] Recurring pattern: 80–120-word sentences chaining 3+ clauses with em-dashes and double parentheticals (worst offenders: §1 para 2 "The off-hour token process is *dual*…", §6.9 (one sentence ≈ 200 words), §9.3 para 2, §7.6.5 closer). The content is good; the sentences need splitting. Rule of thumb for the pass: one claim per sentence, stats in parentheses only when ≤2 per sentence, no nested em-dash chains.
- [ ] The "**bold opening summary sentence** + table + interpretation" pattern in §6/§7 is good — keep it. The problem is only the run-on interpretive paragraphs.

### B7. Overnight panel: emphasis mismatch between front and body
- [ ] Abstract + §1 sell two co-equal panels ("We evaluate on two closed-market panels…"); structurally, overnight is one subsection (§6.8) at the tail of a 9-subsection weekend battery. Two options: (a) promote — give overnight its own §6-level number or split §6 into "Weekend panel" / "Overnight panel" majors; (b) demote the front-matter language to "primary weekend panel + overnight generalisation panel". Option (b) is honest to the evidence weights and costs nothing; option (a) is a bigger lift. Either way, make front and body agree.

### B8. §3 problem statement duplicates §1.1/§2.1 framing
- [ ] §3.2 "The classical oracle problem" re-explains what §1.1's archetype table already established. Tighten §3.2 to two sentences + pointer. (§3 otherwise earns its keep — P1/P2/P3 and the non-goals list are exactly what AFT reviewers want.)

---

## C. Figures — keep / fix / cut / add

Current inventory (10) vs what a bulletproof 8 looks like. AFT carve currently ships only fig1 + fig2 + fig8 — note fig2 is one of the two broken ones (A1/A2).

| Fig | Verdict | Action |
|---|---|---|
| fig0 weekend returns | **KEEP, annotate** | Caption claims BoJ/COVID/tariff "appear as the largest spikes" but the artwork has no event labels — a reader can't tell which spike is which. Annotate the three events (thin vertical markers + small labels). This is the Cong-style "data first" opener; it earns its full page once annotated. |
| fig1 pipeline | **KEEP, redraw** | Only architecture figure. Fix scalar count + receipt duplication (A3); typographic quality is below the rest (boxy, cramped math). One redraw pass in the builder. |
| fig2 calibration | **FIX (A2)** | Regenerate to match caption: M6 + GARCH-t anchor markers + constant-buffer. Drop v0 and M5. |
| fig3 stability | **CUT → appendix** | Both panels are flat-lines-near-nominal; §6.3.3's tables carry identical information with more precision. Low information density. (AFT already excludes it.) Keep in arXiv appendix if desired. |
| fig4 per-symbol | **MERGE or strengthen** | As drawn, it shows only M6 dots inside a wide binomial CI — "nothing happened" visually. The claim is only impressive *against the comparator* (M5: 2/10). Either add grey M5 dots (instant contrast, recommended) or cut fig4 and let fig7b carry the per-symbol story alone. |
| fig5 Pareto | **FIX (A1) or CUT** | After dropping incumbents + v0, what remains (M6 vs GARCH-t, coverage vs width) is one new axis beyond fig2. Option: merge fig2+fig5 into a single two-panel figure (calibration curve | width-at-coverage) and free a slot. |
| fig6 path coverage | **KEEP** | The honesty figure; directional but well-labelled. Appendix in AFT, main text in arXiv. Retitle without "M6". |
| fig7b ablation boxes | **KEEP** | Strongest figure in the paper. Fix title (drop "§7.2"), relabel rows descriptively (A5). |
| fig8 overnight | **KEEP** | Carries §6.8 and the earnings_night over-coverage shape. Fine as is; consider marking Kupiec/Christoffersen pass inline per anchor. |
| simulation_summary | **KEEP** | Fix "Phase 3" title (A5). Romano idiom works here too. |

### C-ADD: the two missing figures (highest-value work in this whole document)

- [ ] **ADD-1: Anatomy of a served band — the BoJ weekend.** The §6.3.5 vignette is the most gripping content in the paper and it's a table. Draw it: x = Fri-close → Mon-open for the 2024-08-02 weekend, per-symbol served bands at τ=0.85/0.95/0.99 (nested shading), realised Monday opens as dots, breaches in red — 10 symbols as small multiples or a compact dumbbell plot of band vs realised move. Instantly communicates: what the product *is*, per-symbol σ̂ width differentiation (MSTR 783bps vs SPY 84bps), and the common-mode joint breach. Cong leads with the concrete TSLAx-premium instance for the same reason. This becomes the paper's signature figure; candidate for Figure 1 position or §6.3.5.
- [ ] **ADD-2: Joint-tail k_w distribution.** C4 ("no incumbent publishes this") is a headline contribution with no visual. Bar chart: empirical P(k_w = k) at τ=0.95 vs Binom(10, 0.05) vs t-copula overlay; mark k*=3 and the BoJ weekend at k=9/10. Pure win from existing tables (`paper1_a3_joint_baseline_kw_distribution.csv`).
- [ ] (Optional ADD-3, cheap): calendar-conditioned widening — band width time-series for one symbol across ~3 weeks straddling an earnings night, showing the deterministic pre-widening. Sells the only *a-priori* regime in one glance. Could live in §4.3.1.

Net: 10 → 9–10 figures but with the two strongest ones added and the two weakest removed (fig3 cut, fig4 merged), every remaining figure self-contained and caption-consistent.

### AFT carve figure plan
- [ ] Current AFT = fig1, fig2, fig8 only. After fixes: fig1 (redrawn), fig2 (fixed), ADD-1 (BoJ anatomy), fig7b, fig8 — five figures in 20 pages, each carrying a distinct claim (architecture / pooled calibration / what-the-product-is / per-symbol ablation / generalisation). ADD-2 if space allows.

---

## D. Smaller wording/consistency items

- [ ] §6.3.2 table: "Kupiec p = 0 (over-covers)" rows — p-values of literally 0 read as placeholder errors; report as "<10⁻⁶" like elsewhere.
- [ ] §9.2 says "2 Kupiec rejections" in the 16-cell sub-period grid; §6.3.3 says "3/16 over-coverage rejections, all in 2025". Reconcile (one of them is stale).
- [ ] §6.3.3.1 table: M_full row shows Christoffersen 0.720 here but 0.603 in §6.3.1 for the same deployed fit — if these are different test variants, say so in the table note; if stale, fix.
- [ ] Hyphenation drift: "tokenised" (UK) vs "tokenized" (US) both appear throughout (§1 uses both in adjacent paragraphs). Pick US (matches "standardised"→ no — the paper uses UK -ise consistently elsewhere: "standardised", "characterised"). Pick UK -ise everywhere, including "tokenised", and sweep.
- [ ] §5.2 says raw panel = "9 full-history symbols × 639 weekends + 245 HOOD weekends" but §5.2 header math gives 5,996; 9×639+245 = 5,996 ✓ — but §5.5 says HOOD contributes "~245" while §6.7 says "246 listed − 28 σ̂ warm-up" → 218. The warm-up drop is stated as 8 per symbol elsewhere (80 rows / 10 symbols). 246−28 vs ≥8-past-obs rule: reconcile the HOOD arithmetic in §6.7.
- [ ] fig2 legend escape bug `F0\_stale` (also fixed by the A2 regeneration).
- [ ] §1 stakes paragraph: "$963M by January 2026" / "~$29B RWA market" — dates will be ~8 months stale at AFT review; add "as of" phrasing so it ages gracefully.
- [ ] quote_bank.md / problem_statement.md are working docs in the same directory as numbered sections — confirm the build script's section glob can never pick them up (it shouldn't; verify once).

---

## E. Suggested execution order (fits part-time slots)

1. **Session 1 (~2h): figures-stale fix.** Edit `build_paper1_figures.py`: fig5 drop incumbents/v0; fig2 → caption-matching design; de-codename all titles/legends; annotate fig0; fix fig1 scalar count + receipt line. Regenerate, rebuild PDFs, eyeball. Closes A1–A5.
2. **Session 2 (~3h): ADD-1 BoJ anatomy figure** (new builder function; data already in the artefact + panel). Wire into §6.3.5. The signature-figure payoff.
3. **Session 3 (~1h): ADD-2 k_w distribution figure** from existing CSVs; wire into §6.3.4.
4. **Session 4 (~3h): intro + abstract rewrite.** Merge double opening (B1), define inversion early (B2), abstract de-mathed (B3), contributions to bold headers (B4).
5. **Session 5 (~2h): dedup pass.** §11 rewrite as interpretation (B5), k* consolidation, §6.9 stays canonical. Sentence-splitting sweep on the worst offenders (B6).
6. **Session 6 (~1h): consistency sweep.** Section D items + §12 figure table (A4) + overnight emphasis decision (B7) + AFT figure set.

Each session ends with `build.py --pdf --aft` + a skim of the changed pages.
