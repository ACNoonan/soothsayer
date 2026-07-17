# Voice & identity

The brand guide for all Soothsayer public copy — README, the landing page
(`landing/`), integration docs, and outreach. If you are writing anything a
non-author will read, read this first.

## The identity

**Infrastructure that earns trust by making itself checkable, not by claiming
to be trustworthy.**

The product's whole thesis is *"don't trust our number — verify our coverage
against public data."* That gives the voice one hard constraint:

> **Never ask for trust the product tells you to verify.**

A single hype sentence undercuts a verify-don't-trust oracle. The medium is the
message. We are, deliberately, the anti-crypto-marketing crypto project — in a
category where every oracle calls itself "the most reliable, institutional-grade,
decentralized," restraint *is* the differentiation. Our readers are risk
engineers, academic reviewers, and protocol partners: to them, underclaiming
reads as confidence and superlatives read as a smell.

## What the four attributes actually signal

| We say | It means (and how we show it) |
|---|---|
| **Open-source** | *Auditable* — every number is reproducible from public data + public code, not just "the repo is public." |
| **Transparent** | *Shows its work, including where it fails* — we disclose the failure mode (pooled DQ rejects) and turn it into reserve guidance (k\*=3); we reported honestly that half the tokenized-tracking edge was calibration history, not architecture. Transparency about **limits** is the credibility signal no competitor offers. |
| **Provable** | *Empirically falsifiable* — the coverage claim can be checked and could be found wrong. Lead with the claim we could lose. |
| **Reliable** | *Boring on purpose* — signalled by parity tests, versioned artifacts, and forward-tape monitoring, never by the word "reliable." |

## Voice rules

1. **Every claim carries its evidence inline.** Never "the best off-hours
   oracle" — always "0.9497 held out by symbol; re-derive it yourself."
2. **Name the limit before a critic does.** The disclosed failure mode is a
   feature of the disclosure.
3. **No adjectival hype.** Numbers with bounds, not superlatives.
4. **Write for the skeptic, not the believer.**
5. **Be compelling through specificity and stakes, not promises.** The vivid
   hook comes from concrete facts (two-thirds of every week; 13.8% of weekends a
   symbol gaps > 500 bps), not from adjectives about the future.

## The hook rule

An aspirational, punchy hook is allowed — *"Real-world assets don't sleep on
the weekend. The promise of tokenized equities is real 24/7… the missing
infrastructure is a defensible closed-market price."* — **as long as the very
next beat grounds it in a measured fact and a falsifiable claim.** Hook, then
substantiate; never leave a promise hanging. The README does this: the tagline
is followed immediately by *"Don't trust the price. Verify the band."* and the
13.8%-of-weekends stat. A promise that stands **alone**, un-grounded, is the
anti-pattern — not the promise itself.

## Anti-patterns (do not ship)

- A vague promise left un-grounded — no measured stake, no falsifiable claim, no
  reproduce-it pointer in the same breath (this is what got struck from the
  paper, `integrity_issues` P1-08/17; the hook rule above is the fix).
- "institutional-grade," "best-in-class," "trustless" as adjectives.
- Any coverage/accuracy claim without its held-out number and a pointer to how
  to reproduce it.

## Taglines to build from

- *Don't trust the price. Verify the band.*
- *A price oracle that publishes its own error bars — and lets you check them.*
