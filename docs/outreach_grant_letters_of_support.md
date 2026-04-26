# Letter-of-Support Outreach — Solana Foundation OEV grant

**Status:** draft templates, 2026-04-25.
**Purpose:** customize-and-send templates for the two letter-of-support requests called for in [`docs/grant_solana_oev_band_edge.md`](grant_solana_oev_band_edge.md) §11.

Both targets are reachable via Superteam Solana (per memory) — prefer warm-intro-then-template over cold-send. Subject-line examples are ready-to-use; bracketed `[FILL]` sections need ~2 minutes per letter to personalise. Each letter is one screen — designed to land in someone's inbox, get read in 60 seconds, and produce a yes/no on the support ask without requiring a follow-up call.

---

## 1. Pyth Data Association — searcher API + LoS

**Target:** Pyth Data Association open-source / research lead. (If using Superteam intros, ask for the Pyth Express Relay technical lead specifically; the BD path is slower for a research deliverable.)

**Channel:** Telegram is faster than email for the Pyth team; email is the formal record.

**Subject:** *Solana Foundation grant request — Pyth Express Relay empirical analysis (xStocks-on-Kamino)*

---

Hi [NAME],

I'm Adam Noonan, working on Soothsayer — a calibration-transparent fair-value oracle for tokenized RWAs on Solana. I'm submitting a Solana Foundation research grant focused on **empirical OEV concentration at oracle-band-edge events on Solana lending protocols**, and Pyth Express Relay is the deployed M1 baseline our analysis runs against. I'd like to request two things from the Pyth Data Association:

1. **A letter of support** for the grant proposal, ideally noting Pyth Express Relay's interest in the type of public-good empirical analysis the grant funds.
2. **Permissioned-searcher API access** for the proposal's deployment phase (months 3–4), so the bot that generates the dataset can actually participate in Express Relay auctions on Kamino xStocks weekend-reopen liquidations.

The grant deliverables are public-good only: an open dataset of xStocks-on-Kamino + MarginFi liquidations 2025-07-14 → grant-end (no comparable dataset exists), an open-source Solana liquidation reconstructor, a peer-reviewable empirical paper targeted at AFT 2026 / FC 2027, and a mechanism-design memo proposing a band-conditional auction overlay on Pyth Express Relay. All artifacts under permissive license. The mechanism-design output is specifically intended to be reviewed by the Pyth Express Relay team — it is not adversarial; it is a deployable improvement under the calibration-transparent oracle assumption.

Why this is timely:
- **Andreoulis et al. (Springer/MARBLE 2025) just published the leading academic OEV analysis on Aave V2/V3.** No equivalent panel exists for Solana. The grant builds the first one.
- **Kamino's September 2025 penalty drop to 0.1%** has materially concentrated the remaining rent at tail / band-edge events — exactly where calibration-aware pricing has an information advantage.
- **MarginFi alone produced ~$88.5M in liquidation fees Q1 2025 across ~9 active liquidators**, an Andreoulis-style coalition concentration that is publicly observable on-chain.

Retrospective evidence already in hand (computed on Soothsayer's 12-year backtest panel, OOS slice 2023+):

- **3.56× median dominance ratio** between band-exit and in-band events at τ=0.95.
- **~21 band-exit events/year** panel-wide (10 symbols × ~52 weekends).
- **$283,745 annual band-aware-vs-band-blind liquidator advantage at $1M working notional**.

The deployed-bot dataset will verify or refine these numbers on real Solana liquidations.

Background on Soothsayer (for context, not as the proposal's subject):
- arXiv submission in flight: *Empirical coverage inversion: a calibration-transparency primitive for decentralized RWA oracles*. 28-reference §2 survey, 12-year backtest, OOS Kupiec/Christoffersen pass at three operating points.
- [GitHub — paper drafts at `reports/paper1_coverage_inversion/`, plan and mechanism-design analysis at `reports/paper2_oev_mechanism_design/`.]

If a 20-minute call works better than email exchange, I'm available [DAYS / TIMEZONE]. Happy to share the full grant proposal draft and the empirical reports under any review process you prefer.

Thank you for the consideration.

Adam Noonan
[ADAM_EMAIL] · adam@samachi.com
[GITHUB / TWITTER / SUPERTEAM PROFILE]

---

## 2. Kamino BD — risk team contact + LoS

**Target:** Kamino BD lead with line into the risk / xStocks integration team. (Marius Ciubotariu, Marius Schober, or whoever is currently fronting the tokenized-RWA conversation; via Superteam intro is preferred.)

**Subject:** *xStocks risk dataset — Solana Foundation grant LoS request*

---

Hi [NAME],

I'm Adam Noonan, working on Soothsayer — a calibration-transparent fair-value oracle for tokenized stocks on Solana. I'm submitting a Solana Foundation research grant focused on building **the first public liquidation dataset for xStocks-on-Kamino**, with reconstructed Soothsayer bands attached to every event, and publishing empirical findings on band-edge OEV concentration.

Kamino is the deployment-target venue for this work — xStocks-on-Kamino is named explicitly in the proposal as the primary panel. I'd like to request a **letter of support** for the grant noting Kamino's interest in the deliverables (and, if useful, an introduction to the right person on the risk side for an ongoing technical dialogue during the dataset construction).

What's in it for Kamino:

- **A public dataset that you don't have to build yourselves** — every xStocks liquidation event from launch (2025-07-14) onward, labelled with the calibration-transparent band Soothsayer would have served at the trigger time, plus reconstructed bid stacks. Released CC-BY.
- **A risk-parameter analysis specifically targeted at Kamino's xStocks markets** — the third paper in this trilogy ([`reports/paper3_liquidation_policy/plan.md`](../reports/paper3_liquidation_policy/plan.md)) is about decision-theoretic LTV/LT defaults under calibrated oracle uncertainty, with Kamino xStocks as the named comparable. The grant work feeds directly into that.
- **A view of where OEV is leaking from your protocol** — the bot that generates the dataset is band-aware, and the dataset records what a band-blind competitor leaves on the table per event. That's a concrete number Kamino's risk team can use to evaluate band-conditional auction overlays on top of Pyth Express Relay (the proposal's mechanism-design output).

Retrospective evidence already in hand (12-year Soothsayer backtest, OOS 2023+, headline target τ=0.95):
- **3.56× dominance ratio** between band-exit and in-band events.
- **~21 band-exit events/year** across the 10-symbol panel (xStocks subset is ~8 of these symbols).
- **$283,745/year band-aware-vs-band-blind liquidator advantage at $1M working notional**.

The grant funds verification of these numbers in production on the Kamino xStocks subset specifically — and the mechanism-design memo at the end is a band-conditional auction overlay you can choose to integrate or not.

The work is non-adversarial. The bot generates ground-truth bid stacks for the dataset; it does not seek to extract value at Kamino's borrowers' expense beyond what's already happening in the current opaque-oracle status quo. If anything, the deployable mechanism overlay this work proposes shifts a fraction of currently-extracted OEV *back* to Kamino borrowers.

Background on the broader project:
- Soothsayer Paper 1 (in submission): *Empirical coverage inversion* — calibration-transparent oracle primitive with 12-year OOS validation.
- Paper 3 (in planning) — decision-theoretic liquidation-policy defaults; Kamino is the named comparable throughout the plan.

If a 20-minute call works for the risk-side conversation, I'm available [DAYS / TIMEZONE]. Happy to share the full grant draft, the trilogy plans, and the empirical reports.

Thank you for the consideration.

Adam Noonan
[ADAM_EMAIL] · adam@samachi.com
[GITHUB / TWITTER / SUPERTEAM PROFILE]

---

## Notes on customization

- **Replace `[NAME]` with the specific contact's name.** Both letters are designed to read as person-to-person rather than form-letter; the cost is ~2 minutes of personalization per send.
- **Trim the retrospective-evidence numbers if the recipient is non-quant.** Kamino BD probably wants the headline (`3.56× / $283k/yr/$1M`) without the panel-scale framing; Pyth research likely wants more.
- **The "what's in it for them" section is the load-bearing one.** For Pyth: research-grade analysis of their deployed system. For Kamino: a dataset they didn't have to build, and risk-parameter work targeted at their venue.
- **If a target says "send the proposal first," send `docs/grant_solana_oev_band_edge.md` and the three empirical reports** as a single PDF bundle. The README of the grant doc has the right framing.
- **If a target is non-responsive, escalate via Superteam intros** (per memory note, you have these ties). A warm intro from someone the target trusts is the single highest-leverage move at this stage.

## What's NOT in scope for these letters

- No revenue ask. The grant is funded by Solana Foundation, not by Pyth or Kamino.
- No equity / token-allocation ask. The relationship is research-deliverable, not commercial.
- No exclusive-data ask. The dataset is public-good — Pyth and Kamino get advance access only to the extent of being letter-of-support contributors with reasonable review windows.

## Pre-send checklist

- [ ] Personalised contact name + opening
- [ ] Solana Foundation grant intake confirmed (open / convertible / etc.) — one-pager templated to that intake's specifics
- [ ] Empirical reports are committed and viewable on GitHub at the linked paths
- [ ] Soothsayer Paper 1 has at least the §1/§2/§3/§6/§9 drafts pushed to a public branch (or the v1b repo state is referenced as the "in-flight" status)
- [ ] Calendly / scheduling link in the email signature
- [ ] Superteam intro path identified for each target (preferred over cold-send)
