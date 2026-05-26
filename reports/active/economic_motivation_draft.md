# DRAFT — economic-importance motivation (data-backed)

**Status:** draft for review (2026-05-25). A reusable motivation block emphasising
*why a calibrated peg-confidence signal matters for the tokenized-equity economy*.
Intended as: the opening hook for the 8-page version; an expanded §1.0 for the
arXiv/AFT versions. Figures are point-in-time (May 2026) and several are from
secondary aggregators — cite the authoritative source and re-verify at submission
(flags below). This is *motivation*, cited like Cong et al.; it does not touch the
model or the scryer data pipeline.

---

## Proposed passage (≈340 words)

**The stakes.** The migration of equities onto programmable rails has left the
experimental phase. The tokenized-equity market grew roughly **2,878% year-on-year
to ~\$963M by January 2026** [coindesk-tokenized-2026]; Ondo Global Markets alone
has cleared **>\$7B in volume** since its September 2025 launch and xStocks
(Backed/Kraken) **>\$10B**, and the broader tokenized-RWA market — near **\$29B**
and growing — is projected by BCG and Standard Chartered to reach **~\$16T,
≈10% of global GDP, by 2030** [bcg-tokenization-2030]. Institutional capital is
committing rather than experimenting: BlackRock's BUIDL (~\$2.5B) is already used
as on-chain collateral for borrowing and leverage [blackrock-24h]. Yet the
distinctive value of a *tokenized* equity — its composability as a building block
for lending markets, AMMs, and programmable settlement — is gated on a trust
precondition a bearer token cannot inherit from its issuer: that its on-chain
price, *at the moment a protocol liquidates, swaps, or values it as collateral*,
is reliably pegged to the underlying. Cong et al. [cong-tokenized-2025] document
that this peg breaks precisely when the underlying venue is closed, and the
incumbent oracle class (§2) supplies *integrity* — a faithful report of the last
value — but not a *calibrated* statement of how far that value may sit from fair
during the closed window. Until a consumer can read that confidence on-chain, the
rational institutional response is to discount or avoid tokenized-equity collateral
exactly where its programmability would otherwise be most valuable.

**Extended hours narrow the window but do not close it.** The market-structure
response is already underway: the SEC has granted preliminary approval for the 24X
Exchange and NYSE Arca's 22-hour (Mon–Thu) schedule, and Nasdaq has proposed
near-24-hour weekday trading, with DTCC and SIP clearing infrastructure targeting
late 2026 [sec-24x; nyse-extended; nasdaq-24h]. But every proposal is **five-day,
retains a maintenance pause, and leaves the weekend — the longest and
highest-variance closed window — entirely uncovered.** Extended hours therefore
*reshape* the closed-market problem (shrinking the weeknight gap, leaving the
weekend) rather than eliminating it. A calibration-transparent peg-confidence
signal is the binding unlock for reliable tokenized-equity collateral and AMMs —
both now and after hours expansion — and is the primitive this paper supplies.

---

## Sourced data table

| Claim | Figure | Source quality | Cite to |
|---|---|---|---|
| Tokenized-equity market YoY growth | ~\$963M, +2,878% (Jan 25→26) | secondary (Phemex) → firm up | CoinDesk 2026-01-30 |
| Ondo Global Markets volume / TVL | >\$7B vol, >\$500M TVL (since Sep 2025) | issuer + press | Ondo / Solana.com |
| xStocks AUM / volume | \$186M AUM (9× in 5mo), >\$10B vol | press | CoinDesk / Kraken |
| Tokenized-RWA total | ~\$29B Q1 2026 (+263% YoY) | aggregator | RWA.xyz / InvestAX Q1'26 |
| BlackRock BUIDL | ~\$2.5B, used as collateral; new SEC filings May 2026 | primary-ish | SEC filing / BlackRock |
| 2030 projection | ~\$16T (~10% global GDP) | analyst | BCG + Standard Chartered |
| 24X / NYSE / Nasdaq extended hours | 24X+NYSE 22h Mon–Thu prelim-approved; Nasdaq near-24h proposed; clearing late 2026 | primary | SEC orders / exchange filings / SIFMA |

**Load-bearing for the argument (must be citation-grade):** the extended-hours
facts (they're what makes "narrows but doesn't close" defensible) and the Cong
peg-break finding (already cited). The market-size figures are supporting colour —
useful but not load-bearing; cite the best available and don't over-anchor on any
single aggregator number.

## Placement
- **8-page version:** this *is* the opening (½ page), establishing stakes before the methodology.
- **arXiv / AFT:** insert as §1.0 / expanded first two paragraphs of §1; reconcile the existing §1 RWA-wave sentence (currently ">\$5B treasuries Q1 2026") with the fresher \$29B-RWA / \$8.7B-treasuries figures.
- New `references.md` entries needed: coindesk-tokenized-2026, bcg-tokenization-2030, blackrock-24h, sec-24x, nyse-extended, nasdaq-24h.
