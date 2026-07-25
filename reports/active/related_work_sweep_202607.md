# Related-work sweep — 2026-07-24

**Status:** working doc. Records a literature sweep run against Paper 1 (`research/coverage-inversion/`) shortly before arXiv submission, the citations added as a result, and the two items deliberately deferred.

**Trigger.** A reader flagged arXiv:2603.22569 (Zhong, *Proxy-Reliance Control in Conformal Recalibration of One-Sided VaR*) as possibly duplicating the deployed method. It does not — but checking it surfaced a neighbourhood Paper 1 had not surveyed, including one paper that makes a §2 novelty sentence falsifiable.

PDFs for everything below are under `research/coverage-inversion/exemplars/related-work-sweep-202607/` (gitignored per `.gitignore:55` — third-party papers are kept locally, not redistributed). All 15 were downloaded from arXiv and each was title-verified against its filename; the four adaptive-conformal IDs were recalled from memory and confirmed by extraction, not assumed.

---

## 1. What the trigger paper actually is

**Zhong 2026** (`zhong-proxy-2026`, arXiv:2603.22569 [q-fin.RM], 23 Mar 2026, USC — *not* Feb 2026).

Nonconformity score and adjustment:

$$u_s^{(\rho)} = \frac{Y_s - \hat q_{\alpha,s}}{v_s^{\rho}}, \qquad \hat q^{\text{adj}}_{\alpha,t} = \hat q_{\alpha,t} + c_{\rho,t}\, v_t^{\rho}$$

with $\rho \in [0,1]$ a **proxy-reliance exponent** on a composite volatility proxy $v$ (20-day realised + GARCH-style + VIX transform). One pooled quantile; **the calibration set is never partitioned**. Six US ETFs (SPY, QQQ, IWM, EEM, GLD, TLT), daily close-to-close, 2015-02-02 → 2025-12-29, 1,730 rolling one-step forecasts per asset. Kupiec + Christoffersen + Engle–Manganelli DQ + tick loss + a stress-conditional exceedance rate.

Assessed against the initial report:

| Claim made about it | Verdict |
|---|---|
| "regime-conditioned empirical calibration surfaces" | **No.** No Mondrian, no group-conditioning, no partition — scale normalisation only |
| "distribution-free one-sided coverage" | **No.** Explicitly disclaims it: Props 4.1–4.3 are "mechanism-based structural properties under stylized local assumptions, rather than finite-sample guarantees for the full rolling procedure". No exchangeability assumption stated |
| "proxy-reliance names our buffer/regime dependence" | **Partly** — see §3 below; it names a real axis we fixed without ablating |
| "validated with Kupiec and Christoffersen" | **Yes**, plus DQ. But these are the standard VaR backtests since 1995/1998; shared use is not evidence of method overlap |

No crypto, tokenised assets, oracles, market closure, or weekend/overnight gaps anywhere in the paper.

**Also:** the reader's "Feb 2026" description conflated Zhong with Schmitt (§2), a genuinely distinct Feb-2026 paper whose *title* contains "regime-weighted". Both are real; they are different papers on different axes.

---

## 2. The two findings that mattered

### 2.1 ACon² — makes a §2 sentence falsifiable  🔴

`acon2-2023` — Park, Bastani & Kim, **USENIX Security 2023** (arXiv:2211.09330 [cs.CR]).

`02_related_work.md:3` claimed three literatures "have, to our knowledge, never been brought together": oracle design, price discovery, conformal calibration. ACon² joins oracle design and conformal prediction, at a top-tier security venue, three years before us, and was uncited anywhere in `research/`.

What it does: derives a **consensus set** across multiple oracle contracts via online uncertainty quantification, with a correctness guarantee holding under distribution shift *and Byzantine adversaries*. Demonstrated on Ethereum DEX/CEX price data (INV/ETH across SushiSwap, UniswapV2, Coinbase) with a Solidity implementation.

Why it does **not** subsume the contribution — and in fact sharpens it:

| | ACon² | Paper 1 |
|---|---|---|
| Source of uncertainty | Disagreement among concurrently-reporting sources; adversarial corruption | A single reference market being **closed** |
| Reducible? | Yes — add honest reporters | No — structural; nobody can observe Monday's open on Sunday |
| Interval means | "contains the honest value despite liars" | "contains the realised reopen price at rate τ" |
| Consumer-chosen τ on the wire | No | Yes |
| Re-derivable receipt | No | Yes |
| Market closure / RWA | Absent | The entire object |

ACon² is **conformal-as-integrity**. §2.1 already argues the integrity/calibration distinction abstractly; ACon² is the concrete instance that proves the distinction is not a strawman — a conformal oracle that still makes no calibration claim about a closed market. Cited and distinguished rather than avoided.

### 2.2 No adaptive-conformal baselines in §7  🟠

`schmitt-rwc-2026` — Marc Schmitt (Oxford), *Taming Tail Risk: Regime-Weighted Conformal Calibration for Nonstationary VaR* (arXiv:2602.03903v2 [q-fin.RM], 3 Feb 2026, rev 13 Jul 2026).

RWC wraps any quantile forecaster and calibrates an **additive safety buffer** from past errors, weighted by exponential time decay × regime similarity (TWC = the kernel-free special case). Its coverage-gap bound holds for arbitrary data-driven weights by conditioning on the regime path and exploiting total-variation smoothness of the score distribution — explicitly *avoiding* an assumption of weighted exchangeability w.r.t. its own weights. CRSP value-weighted index + 16 CRSP-derived portfolios, 1990–2024, at 99% and 97.5%.

It is benchmarked against **ACI, DtACI, and conformal PID control**. Paper 1's §7 comparator set is GARCH-$t$, GARCH-Gaussian, unweighted Mondrian, constant buffer — every one either parametric or an internal ablation. **Zero adaptive-conformal baselines.** That is the first question a conformal-literate reviewer asks, and it is a larger exposure than the $\rho$ axis.

Canonical family: `gibbs-aci-2021` (arXiv:2106.00170), `gibbs-dtaci-2022` (2208.08401), `zaffran-agaci-2022` (2202.07282), `angelopoulos-pid-2023` (2307.16895).

Schmitt is complementary, not competing: continuous regime *weights* rather than a Mondrian partition, index/portfolio-level series with no per-symbol calibration claim, and no closed-market, oracle, or tokenised dimension. His guarantee technique is a plausible replacement for the §4.3 within-bin exchangeability argument, which we currently support empirically (permutation test, §A.9) rather than theoretically.

---

## 3. The ρ axis — endpoints ablated, interior not

Zhong's $\rho$ names something Paper 1 fixed silently. In his parameterisation:

- $\rho = 0$ → approximately constant additive shift ≈ the **§7.1 constant-buffer comparator** (17/40 per-symbol Kupiec)
- $\rho = 1$ → fully proxy-scaled correction ≈ the **deployed σ̂-standardised score** (40/40)

So both *endpoints* of the axis are already ablated in §7.1/§7.2, and the *interior* is not. Zhong's finding is that intermediate $\rho$ can beat $\rho = 1$ under stress, because a proxy that underreacts in a shock drags the whole adjustment down with it.

Grep confirms no exponent/scale-exponent discussion anywhere in `reports/methodology_history.md` or `reports/active/m6_refactor.md` — this was never a considered-and-rejected choice, it was never considered. Logged to §10 future work and to the validation backlog; a $\rho \in \{0, 0.25, 0.5, 0.75, 1\}$ sweep on the existing weekend panel is cheap (endpoints already computed).

---

## 4. Supporting citation — the §7.2 mechanism, replicated

`socio-conformal-2026` — Rafe & Das (Texas State), *Socio-Conformal Calibration in Complex Survey Data: Marginal Validity Is Not Enough for Subgroup Reliability* (arXiv:2605.05562 [stat.ME], 7 May 2026).

They report standard split-conformal attaining nominal **marginal** coverage on the Pew American Trends Panel while carrying **~13-percentage-point weighted subgroup gaps**, produced by compensating over- and under-coverage across race–education subgroups. That is §7.2's mechanism verbatim ("pools to nominal *through compensating per-symbol biases* — heavy-tail tickers under-cover, low-vol tickers over-cover"), independently reproduced in a completely different domain.

The genuinely useful part is their **negative** result: a group-specific (Mondrian) threshold made the fairness/efficiency trade-off *worse* in their setting, and a regularised shrink-to-global comparator only marginally helped. Regime partitioning alone does not recover subgroup calibration. That is exactly why the deployed architecture standardises by per-symbol σ̂ *before* fitting the per-regime quantile, rather than adding a per-(symbol, regime) Mondrian rung — which §4.3 rejected on cell-thinness grounds. It reframes §7.2 from "we ran an ablation" to "we solved a mechanism documented across domains, whose obvious fix does not work."

---

## 5. Citations added

| Key | Paper | Section |
|---|---|---|
| `acon2-2023` | ACon²: Adaptive Conformal Consensus for Provable Blockchain Oracles (USENIX Sec'23) | §2 intro, §2.1 |
| `sok-rwa-2026` | Luo et al., SoK of RWA Tokenization (q-fin.GN) | §2.1 |
| `schmitt-rwc-2026` | Schmitt, Regime-Weighted Conformal Calibration for Nonstationary VaR | §2 intro, §2.3 |
| `zhong-proxy-2026` | Zhong, Proxy-Reliance Control in Conformal Recalibration of One-Sided VaR | §2 intro, §2.3 |
| `gibbs-conditional-2025` | Gibbs, Cherian & Candès, Conformal Prediction with Conditional Guarantees (JRSS-B) | §2.3 |
| `gibbs-aci-2021` | Gibbs & Candès, Adaptive Conformal Inference Under Distribution Shift | §2.3 |
| `gibbs-dtaci-2022` | Gibbs & Candès, Conformal Inference for Online Prediction with Arbitrary Distribution Shifts | §2.3 |
| `zaffran-agaci-2022` | Zaffran et al., Adaptive Conformal Predictions for Time Series | §2.3 |
| `angelopoulos-pid-2023` | Angelopoulos, Candès & Tibshirani, Conformal PID Control | §2.3 |
| `wang-qrf-var-2026` | Wang et al., Real-Time VaR via Quantile Regression Forest with Conformal Calibration | §2.3 |
| `tcp-2025` | Aich et al., Temporal Conformal Prediction | §2.3 |
| `cuonzo-tail-2026` | Cuonzo & Deliu, Conformal Prediction Intervals with Tail-Specific Guarantees | §2.3 |
| `socio-conformal-2026` | Rafe & Das, Marginal Validity Is Not Enough for Subgroup Reliability | §7.2 |

Held locally, not cited: `zhong-reliability-2026` (arXiv:2604.08765, ETF tail-risk monitoring — adjacent, systems framing) and `conformal-action-conditional-2026` (arXiv:2606.05551, action-conditional VaR — routed to **Paper 3**, whose shape it closely matches).

**Not obtained:** the cross-index overnight→morning-gap forecasting paper (ScienceDirect S2214845026000918) is paywalled. Relevant to §6.8; not cited pending access.

---

## 6. Deferred — not done in this pass

1. **ACI / DtACI / conformal PID as §7 baselines.** The substantive gap (§2.2). Real compute; scope decision on a paper at human-review. ACI alone is a small addition against the existing harness.
2. **ρ ∈ {0, 0.25, 0.5, 0.75, 1} sweep** (§3). Endpoints already computed.

Both are logged to `reports/active/validation_backlog.md`.

---

## 7. arXiv endorsement candidates (q-fin.RM)

Endorsement requires a prior q-fin.RM submitter. **Verified primary-category `q-fin.RM`** by extracting the stamp from each PDF:

- **Marc Schmitt** — University of Oxford, `marc.schmitt@cs.ox.ac.uk` — arXiv:2602.03903 [q-fin.RM]. Closest methodological neighbour; would be cited by us.
- **Tenghan Zhong** — University of Southern California — arXiv:2603.22569 and arXiv:2604.08765, both [q-fin.RM].

Everything else in this sweep is stat.ME / stat.ML / math.ST / cs.LG / cs.CR / q-fin.GN and does **not** qualify. (An earlier pass wrongly listed the tail-specific-guarantees authors as candidates; that paper is math.ST.)

Endorsement outreach itself is tracked in the gitignored `arxiv-endorsement/` directory.
