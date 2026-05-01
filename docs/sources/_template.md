# `<Venue> <Version>` — Methodology vs. Observed

> **Canonical structure.** Copy this file when adding a new source. Every section is required; if a section is genuinely empty (e.g. no observed data yet), state that explicitly rather than deleting the heading. The whole point of this doc set is that "we don't know" is a finding, not a gap to hide.

---

**Last verified:** `YYYY-MM-DD`
**Verified by:** `<docs URL #1>`, `<docs URL #2>`, `<on-chain probe / scryer parquet path>`
**Version pin:** `<exact version string>` (first-live `YYYY-MM-DD`; superseded `<version>` on `YYYY-MM-DD`)
**Role in soothsayer stack:** `observation input` | `comparator` | `consumer target` | `issuer ground truth`
**Schema in scryer:** `dataset/<venue>/<data_type>/v<N>/...` (or `not in scryer`)

---

## 1. Stated methodology

What the **public docs** of this venue claim. Extract formulas, code tables, cadence promises, and fallback rules verbatim or paraphrased — with quote marks where exact wording matters and section anchors back to the source URL.

If the methodology is **partially or fully undisclosed**, say so here in §1 and use §3 to record what *can* be inferred from the public surface.

Required sub-sections, in order:

1.1 **Aggregation / pricing rule.** What goes in (sources, weights), what comes out (price + optional confidence).
1.2 **Cadence / publication schedule.** How often, during which market windows, and what the venue claims happens during off-hours.
1.3 **Fallback / degraded behavior.** What the docs say happens when inputs are missing, stale, or rejected.
1.4 **Schema / wire format.** Exact field names + types, ABI / IDL pinning where applicable.

## 2. Observable signals (where this lives in our data)

How the stated mechanism realizes inside soothsayer's read path.

- **Scryer parquet:** `dataset/<venue>/<data_type>/v<N>/...` — list partition layout + the reader function in `src/soothsayer/sources/scryer.py:<line>`.
- **On-chain account / program** (if applicable): exact addresses, IDL pin under `idl/<venue>/`, decoder location under `src/soothsayer/<venue>/`.
- **Decoder / loader:** specific code paths — file + line — that map the wire schema in §1.4 to the columns we actually query.
- **Coverage in current tape:** date range, frequency, gaps. If the column we care about is empty in our tape, say so here.

## 3. Reconciliation: stated vs. observed

The heart of the file. **Specific cells** where the docs claim X and our tape shows Y — or where we cannot tell from the public surface and have ruled the question open.

Required structure: a small table or numbered list, each row of the form **claim → observation → verdict**.

- **`<docs claim, paraphrased>`** — observed in `<scryer query / report path>`: `<concrete number, sample, or "not measurable">`. Verdict: **confirmed** | **contradicted** | **unmeasurable from public surface**.

If the venue's docs are silent on something we observe, that goes here too (e.g., "docs do not describe weekend behavior; we observe `.01` synthetic markers").

## 4. Market action / consumer impact

When does this venue's behavior change a real downstream decision? **At least one non-Kamino downstream consumer must appear in this section before the file is considered complete** — soothsayer's wider goal is to characterise off-hours fair value across the lending stack, not to over-fit Kamino.

Examples of the kind of impact this section catalogues:

- Has this venue's price ever flipped a Kamino `PriceHeuristic` or MarginFi oracle-validity check to invalid?
- Did this venue's weekend print drive a Drift mark dislocation or a Hyperliquid funding spike?
- Is its funding rate / dispersion measure a leading or lagging signal vs. the Monday gap?

Each impact claim must cite either a scryer-query result, a report under `reports/`, or be marked `TODO when scryer item N lands` with the specific scryer wishlist item that gates measurement.

## 5. Known confusions / version pitfalls

Things a future reader (or a re-read by us) would re-confuse without this section.

Required to cover:
- **Version drift** — when the venue silently changed schemas, formats, or feeds (e.g., Chainlink v10 → v11; Pyth regular vs Pull vs Lazer).
- **Naming collisions** — when this venue uses the same word for different objects than another venue (e.g., "mark" on Drift ≠ "mark" on Kraken Perp).
- **Region / access pitfalls** — geo-blocks, deprecated endpoints, undocumented retention caps.

## 6. Open questions

Things we genuinely cannot answer from the public surface today. Each entry has:
- the question,
- why it matters (which paper / decision depends on it),
- the gating action (outreach to which contact, which scryer wishlist item, which on-chain probe).

This section is **append-only as research lands**: do not delete entries when they get answered; mark them resolved with a date and a pointer to the §3 row that absorbed the answer.

## 7. Citations

Bibtex-style entries with **accessed-on dates**. Web pages drift; the accessed-on date is the only durable anchor. Format:

```
[<tag>] <Author/Org>. <Year>. *<Title>*. <Venue / URL>. Accessed: YYYY-MM-DD.
```

Cross-references to internal repo artifacts (reports, code, parquet) go inline in §1–§6 as `path:line`, not in §7.

---

## Lifecycle hygiene

- When the venue ships a breaking schema change, **fork** the file (e.g., `chainlink_v11.md` + `chainlink_v12.md`) rather than overwrite. The old version stays as a historical record because the schema we *had* in our tape still anchors past calibration runs.
- When a §6 open question resolves, move the answer into §3 *and* link from §6 with a resolution date. The §6 entry stays.
- The `Last verified` date is mandatory and should be re-stamped on every substantive edit.

---

*Template version: 1.0 (2026-04-29).*
