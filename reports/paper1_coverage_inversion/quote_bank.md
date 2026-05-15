# Paper 1 — Quote Bank

Collected quotes (from exemplar papers, industry pieces, blog posts, our own scratchpad) that we may want to cite, adapt, or paraphrase when drafting paper 1.

**Per-entry format:**

- **Source** — pointer to the original (exemplar file + manuscript page, URL, etc.). Quotes must be verbatim so they remain citation-safe; light formatting fixes (hyphenation, line breaks from pdftotext) are fine, content edits are not.
- **Quote** — the passage itself, blockquoted.
- **Use** — where in our paper it would land, and what we'd actually do with it (paraphrase, contrast, direct cite). This is the line that earns its keep.
- **Tags** — short comma-separated labels for grep (`#definition`, `#framing`, `#critic-concerns`, `#methodology`, `#numbers`, …).

When adding a new entry, increment the Qn counter and put new entries at the bottom unless you have a reason to group. Search by tag (`grep -i '#critic-concerns' quote_bank.md`) or by source (`grep 'Cong' quote_bank.md`).

---

## Q1 — Definition + proponent/critic framing of tokenized equities

**Source:** Cong, Landsman, Rabetti, Zhang, Zhao (Dec 2025), *Tokenized Stocks* — `exemplars/Tokenized-Stocks-Cong/01_introduction.txt`, manuscript p. 3 (opening paragraph).

> Tokenized equities are essentially digital bearer instruments backed one-for-one by shares held in custody and settled on public blockchains. They trade globally, near-instantly, and 24/7 in fine increments, unhindered by the traditional exchange hours of 9:30–4:00 ET. Proponents of tokenized assets posit that tokenization can enhance price discovery and market efficiency by allowing investors to react immediately to news in a 24-hour news cycle and by democratizing access to global markets. Critics, however, highlight risks including thin liquidity, regulatory grey areas, and potential mispricing on these unofficial venues. After-hours trading typically suffers from low volume and wide spreads, making prices more volatile and executions costlier. Observers note that decentralized token markets lack the protections of traditional exchanges—there are no circuit breakers or unified oversight—raising concerns about manipulation or insider trading.

**Use:** Paper 1 §1 (Introduction) opening, possibly mirrored in §2 (Background). The first sentence is the cleanest one-line *definition* of a tokenized equity I've seen — we can paraphrase it as our own definition and cite Cong et al. The proponent/critic dichotomy in the second half is exactly the tension our oracle resolves: arbitrage works (proponents) *but* off-hour thin liquidity and the absence of circuit breakers create mispricing risk that on-chain price feeds inherit (critics). Cite at the point where we motivate why naive price-feed forwarding is unsafe.

**Tags:** #definition #framing #proponent-critic #citation-ready #intro #off-hours

---

## Q2 — Backed vs Ondo: platform design drives off-hour price quality

**Source:** Cong et al. (Dec 2025), *Tokenized Stocks* — `exemplars/Tokenized-Stocks-Cong/02-2_backed_xstocks_vs_ondo.txt`, manuscript pp. 10–11 (§2.2).

> Backed's tokens trade continuously on decentralized exchanges across multiple blockchains, supporting active weekend and overnight trading by a broad base of retail participants. In contrast, Ondo's tokens synchronize creation and redemption with U.S. market hours, resulting in an effective 24/5 structure and more limited off-hour activity. As a consequence, whereas Ondo's token prices tend to remain tightly anchored to the underlying during weekdays, Backed's tokens exhibit greater off-hour price variation and participation. These contrasts illustrate that continuous market access does not guarantee uniform liquidity at all times; instead, market quality depends critically on platform design and participant composition.

**Use:** Strong material for §2 (Background) where we introduce the issuer landscape, and again in §6 (Discussion / Limitations) when we explain why a single fixed oracle band would fail across issuers. The closing sentence — "market quality depends critically on platform design" — is exactly the empirical observation that *motivates* per-venue calibration: the same nominal "24/7 tokenized equity" produces a quiet 24/5-effective process (Ondo) or an active 24/7 process with mixed signal+noise (Backed), and an oracle has to handle both. Pair with Q1 for a "proponents/critics — but actually it's design-dependent" three-beat opener.

**Tags:** #issuer-design #platform-comparison #backed #ondo #off-hours #microstructure #motivates-calibration

---

## Q3 — Continuous trading extends price discovery, but thin liquidity produces NYSE-halt-class moves

**Source:** Cong et al. (Dec 2025), *Tokenized Stocks* — `exemplars/Tokenized-Stocks-Cong/01_introduction.txt` lines 124–135, near end of §1 Introduction, manuscript pp. 6–7.

> At the same time, the costs of thin liquidity are evident in higher short-term volatility and occasional price dislocations. Regulatory commentary has noted these concerns: token venues operate in a gray area without the standard investor protections or circuit breakers of traditional exchanges. Indeed, we observe that extreme movements can occur on token exchanges that likely would have triggered halts in regulated markets. Nonetheless, our evidence suggests that continuous trading can extend price discovery across temporal boundaries—weekend token trading often foreshadows the direction of Monday's stock moves, smoothing what might otherwise be a sharp gap at the open. In this sense, tokenization offers a glimpse of what a future with nearly continuous equity trading might look like if broadly adopted, which comes timely given Nasdaq's recent proposal to extend trading hours. It shows both the potential benefits of moving beyond the 9:30–4:00 paradigm, such as timelier information incorporation and broader global access, and the associated challenges, including liquidity fragmentation and regulatory arbitrage. Our findings thus have implications for market efficiency, the design of trading platforms, and even corporate disclosure policies in a world where markets never sleep.

**Use:** This is the strongest single passage in the paper for our §1 contribution framing. Cong et al. have laid out the *exact problem* we solve, without solving it: continuous-trading tokens carry real price-discovery signal (weekend moves foreshadow Monday opens) *and* exhibit prints that would have triggered NYSE halts in regulated markets. Their implicit ask is "we need investor protections in this regime"; our paper's answer is "we provide one — a coverage-calibrated band that downstream consumers can use as a circuit-breaker analog at the consumer layer rather than the venue layer." Cite this in §1 as the empirical problem statement, then position our calibrated band as the *risk-side complement* to their conditional-mean signal: Cong shows the signal exists (λ=0.903), we provide a calibrated quantile band so consumers can use that signal without inheriting the prints that would have been halted.

The framing is structurally parallel to LVR-aware AMM designs (e.g., Sorella's Angstrom, prop-AMM bets generally): both ingest the venue's true price process, then build a risk-protective wrapper around it that lets the signal through while bounding the consumer's exposure to the venue's microstructure noise. Same architectural shape applied to a different consumer surface.

**Tags:** #contribution-framing #price-discovery #circuit-breaker #consumer-layer #lvr-analog #monday-open #intro #citation-ready


