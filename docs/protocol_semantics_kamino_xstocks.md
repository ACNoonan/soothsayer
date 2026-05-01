# Kamino-xStocks Lending Market — Verified Action Semantics

**Last verified:** 2026-05-01
**Version pins:** klend IDL v1.19.0 (`idl/kamino/klend.json`); Scope IDL v0.33.0 (`idl/kamino/scope.json`); on-chain reserve config snapshot 2026-04-27 (`data/processed/kamino_xstocks_snapshot_20260427.json`).
**Lending market:** `5wJeMrUYECGq41fxRESKALVcHnNX26TAWy4W98yULsua` (the xStocks market — all 8 xStock reserves live here).
**Klend program:** `KLend2g3cP87fffoy8q1mQqGKjrxjC8boSyAYavgmjD`.
**Scope program:** `HFn8GnPADiny6XqUoWE8uRPPxb29ikn4yTuPa9MF2fWJ`.

This is the canonical end-to-end reference Paper 3 §6 cites for "what does Kamino actually do on xStocks." It supersedes the stylized `Safe/Caution/Liquidate` ladder in `crates/soothsayer-demo-kamino/src/lib.rs`, which is a demo abstraction, not a verified semantics document. Pin a `Last verified` date on every substantive edit.

The roadmap (`docs/ROADMAP.md` §"Must fix before Paper 3 is credible" #1) requires this file to be backed by real on-chain config and IDL decode rather than reserve params alone — that's what's done here.

---

## 1. Oracle path: Scope is the only active source

The xStocks reserves wire **Scope only**. Pyth (`token_info.pyth.active = false`) and Switchboard (`token_info.switchboard.active = false`) are inactive on all 8 reserves. This is empirical (snapshot 2026-04-27), not a documentation claim.

Implication: a single Scope outage simultaneously degrades all 8 reserves' price feeds. There is no oracle redundancy on the xStocks lending market today. (See `docs/sources/oracles/scope.md` §4 for the broader implication and the Sunday-stale-hold finding.)

### 1.1 Feed wiring — all 8 reserves share one PDA

All 8 xStock reserves point at Scope `OraclePrices` PDA `3t4JZcueEzTbVP6kLxXrL3VpWx45jDer4eqysweBchNH`. Differentiation is by `price_chain` and `twap_chain` — chain indices into the `[DatedPrice; 512]` array.

| Symbol | spot `price_chain[0]` | TWAP `twap_chain[0]` |
|---|---:|---:|
| SPYx | 344 | 279 |
| QQQx | 347 | 281 |
| TSLAx | 338 | 273 |
| GOOGLx | 326 | 265 |
| AAPLx | 317 | 259 |
| NVDAx | 332 | 269 |
| MSTRx | 335 | 271 |
| HOODx | 320 | 261 |

(Trailing chain slots are `65535` — sentinel for "no further hop.") The single `getAccountInfo` against the OraclePrices PDA reads all 8 prices via local slicing — efficient, but it also means one Scope account write touches all 8 simultaneously.

### 1.2 Staleness rule

Per `token_info.max_age_price_seconds = 300` (all 8 reserves; GOOGLx has `max_age_twap_seconds = 500`, the rest are 300). A Scope spot-price record older than 300 seconds is rejected for that reserve. The rejection cascades:

- if the spot fails the age check, the reserve cannot price the asset;
- consumer instructions (deposit, borrow, repay, liquidate) read the price; if the read fails, the instruction reverts.

The Sunday 2026-04-26 stale-hold finding in `docs/sources/oracles/scope.md` §3 documents that during weekends Scope's `unix_timestamp` rotates fresh while the underlying `price` value does not change — the staleness check passes even though no real price discovery is occurring. **This is the canonical closed-market failure mode the soothsayer band is calibrated against.**

### 1.3 TWAP divergence defense

Per `token_info.max_twap_divergence_bps = 500` (all 8): if the spot price deviates from the Scope TWAP by more than 5% (500 bps), the price read is rejected. The TWAP feed is the secondary chain index above; both feeds live in the same Scope `OraclePrices` PDA.

This is Kamino's primary on-chain price-validity defense. It does **not** widen with closed-market regime — it's a static threshold. A weekend xStock dislocation that exceeds 5% from the (also-stale-held) TWAP would be rejected, which **blocks all borrow / repay / liquidate operations** until the divergence narrows.

### 1.4 PriceHeuristic guard rail

Per `token_info.heuristic = { lower_raw, upper_raw, exp }`: a fixed price band the on-chain oracle read must fall within. Outside the band → price rejected → operations revert. Per-reserve values (snapshot 2026-04-27):

| Symbol | Lower | Upper | Spot at snapshot (Friday close) | Headroom |
|---|---:|---:|---:|---|
| SPYx | $515 | $858 | $713.94 | 28% / 17% |
| QQQx | $400 | $700 | $663.88 | 40% / 5% |
| TSLAx | $300 | $520 | $376.30 | 20% / 28% |
| GOOGLx | $224 | $416 | $344.40 | 35% / 17% |
| AAPLx | $190 | $300 | $271.06 | 30% / 10% |
| NVDAx | $100 | $250 | $208.27 | 52% / 17% |
| MSTRx | $65 | $250 | $171.02 | 62% / 31% |
| HOODx | $54 | $100 | $84.71 | 36% / 15% |

QQQx's 5% upper headroom is structurally tight; AAPLx's 10% upper headroom is tight. A weekend gap up of those magnitudes would invalidate the price for those reserves regardless of soothsayer's served band, blocking liquidation.

**This is a critical Paper 3 finding.** The PriceHeuristic is a *validity gate*, not a coverage band — and on QQQx and AAPLx specifically, the upper bound is close enough to recent spot that a moderate adverse weekend move could flip the heuristic rather than triggering a liquidation. The protocol's response is "block, don't liquidate." That's a different failure mode than reserve-buffer exhaustion and Paper 3 must distinguish them.

---

## 2. Reserve parameters (8 xStocks, snapshot 2026-04-27)

Static governance parameters from `ReserveConfig` (`idl/kamino/klend.json:7685-7878`):

| Symbol | LTV | Liq thr | Gap (pp) | Borrow factor | Min/max bonus | Bad-debt bonus | Protocol fee | Borrow limit |
|---|---:|---:|---:|---:|---|---:|---:|---|
| SPYx | 73 | 75 | 2 | 166% | 5%–10% | 0.99% | 50% | 5,000.0 SPYx |
| QQQx | 70 | 72 | 2 | 166% | 5%–10% | 0.99% | 50% | 1,000.0 QQQx |
| TSLAx | 55 | 65 | 10 | 225% | 5%–10% | 0.99% | 50% | 2,500.0 TSLAx |
| GOOGLx | 60 | 70 | 10 | 200% | 5%–10% | 0.99% | 50% | 0 (deposit-only) |
| AAPLx | 40 | 50 | 10 | 200% | 5%–10% | 0.99% | 50% | 0 (deposit-only) |
| NVDAx | 55 | 65 | 10 | 225% | 5%–10% | 0.99% | 50% | 500.0 NVDAx |
| MSTRx | 30 | 40 | 10 | 250% | 5%–10% | 0.99% | 50% | 0 (deposit-only) |
| HOODx | 30 | 40 | 10 | 250% | 5%–10% | 0.99% | 50% | 0 (deposit-only) |

Decoded from snapshot:
- **`loanToValuePct`** (`u8`) — max-LTV at origination. A new borrow is rejected if it would push the obligation past this LTV.
- **`liquidationThresholdPct`** (`u8`) — LTV above which the obligation is liquidatable.
- **`borrowFactorPct`** (`u64`, in %) — risk multiplier when this asset is borrowed against. A $100 borrow of SPYx counts as $166 of effective debt for the borrower's health calc; a $100 borrow of MSTRx counts as $250. **This compounds with the lender-side haircuts and is easy to miss when reasoning about MSTRx/HOODx exposure.**
- **`minLiquidationBonusBps` / `maxLiquidationBonusBps`** — the dynamic bonus floor and ceiling. Actual bonus on a given liquidation is somewhere in `[5%, 10%]`; the curve formula is in program logic, not surfaced in the IDL or snapshot (see §6 open questions).
- **`badDebtLiquidationBonusBps`** — flat 0.99% bonus when the obligation is undercollateralized (asset value < debt). The low value reflects that there's no "above-debt" collateral to award the liquidator from; this is salvage.
- **`protocolLiquidationFeePct`** (50 on all 8) — the protocol takes 50% of whatever liquidation bonus is paid; the liquidator receives the remaining 50%. So a 10% bonus pays the liquidator 5% net.
- **`borrowLimit = 0`** on GOOGLx, AAPLx, MSTRx, HOODx — these are deposit-only collateral reserves; users can deposit + use as collateral but cannot borrow these tokens. Liquidation-bonus arithmetic still applies when these are seized.

All 8 reserves share `min_liquidation_bonus_bps = 500`, `max_liquidation_bonus_bps = 1000`, `bad_debt_liquidation_bonus_bps = 99`, `protocol_liquidation_fee_pct = 50`. Where parameters vary per-asset, the riskier assets (TSLAx, NVDAx, MSTRx, HOODx) carry higher borrow factors and lower LTV/liq-threshold gaps.

---

## 3. Liquidation trigger condition

A user's `Obligation` becomes liquidatable when its weighted health factor falls below `1.0`, where the health factor is computed using each reserve's `liquidation_threshold_pct` (collateral side) and `borrow_factor_pct` (debt side). Concretely, for a single-collateral / single-debt obligation:

```
collateral_value_at_liq_thr = collateral_amount × oracle_price × (liquidation_threshold_pct / 100)
debt_value_borrow_adjusted  = debt_amount       × oracle_price × (borrow_factor_pct       / 100)
health                      = collateral_value_at_liq_thr / debt_value_borrow_adjusted
liquidatable iff health < 1.0
```

For multi-asset obligations, the numerator and denominator sum across all collateral and debt positions respectively. The trigger is purely price-driven once the obligation exists; there is no time-based flag, no "wait for market open" gate, and no manual liquidator approval step.

**Critical**: the trigger reads the *current* Scope spot price, subject to (i) the 300s staleness gate (§1.2), (ii) the 5% TWAP divergence gate (§1.3), and (iii) the PriceHeuristic guard rail (§1.4). If any of these fails, the price read fails, **the liquidation cannot fire**, and the obligation persists until the gate clears. This is the closed-market deferral behavior — implicit, not explicit.

There is no published formal soft-liquidation trigger condition (§6 open question). The auto-deleverage path (§4.3) is the closest IDL-pinned graduated-response mechanism; it is **disabled on all 8 xStock reserves** (`autodeleverage_enabled = 0`).

---

## 4. Liquidation arithmetic and protocol-loss accounting

### 4.1 The healthy-but-liquidatable case (most common)

The obligation is past `liquidation_threshold_pct` but the collateral is still worth more than the debt. The liquidator repays a portion of the debt and seizes a corresponding amount of collateral plus a bonus.

Let:
- `P_oracle` = Scope-served oracle price (post-validity gates)
- `D_repaid` = USD value of debt the liquidator repays in the instruction
- `C_seized` = USD value of collateral the liquidator receives

```
bonus_pct  = clamp(curve(health), min_liquidation_bonus_bps/10000, max_liquidation_bonus_bps/10000)
                                                        // ∈ [5%, 10%] for all xStock reserves
C_seized   = D_repaid × (1 + bonus_pct)
liquidator_takes  = C_seized × (1 − protocol_liquidation_fee_pct/100) − D_repaid
                  = D_repaid × bonus_pct × (1 − 0.50)
                  = D_repaid × bonus_pct × 0.50              // 50% of the bonus, post protocol cut
protocol_takes    = D_repaid × bonus_pct × 0.50              // the other 50%
borrower_loses    = C_seized − D_repaid = D_repaid × bonus_pct
                                                        // ∈ [5% × D_repaid, 10% × D_repaid]
```

The exact `curve(health)` is not surfaced in the IDL; it's program logic. The empirical floor cited in `reports/kamino_liquidations_first_scan.md:53` ("Kamino's median liquidation penalty dropped to 0.1% in September 2025") refers to a *different* product surface than the regular liquidation path here — likely soft-liquidations / deleveraging on other markets where `autodeleverage_enabled = 1`. For the xStocks lending market specifically, the bonus is gated by `[5%, 10%]` per snapshot.

### 4.2 The bad-debt case (collateral worth less than debt)

When the obligation has crossed `liquidation_threshold_pct` and continued past 100% LTV (the collateral is now worth less than the debt), the liquidator receives the flat `bad_debt_liquidation_bonus_bps = 0.99%`. The collateral-shortfall vs. debt is the protocol's bad-debt residual:

```
C_seized  = D_repaid × 1.0099                        // bonus is 0.99%, applied to repaid debt
bad_debt  = D_outstanding_at_event − C_seized        // protocol-owned residual
```

`bad_debt` is socialized to the reserve's depositors via reduced cToken redemption value (per Kamino's design). There is no explicit insurance-fund subsidy for xStock reserves at the snapshot date.

### 4.3 The auto-deleverage path (currently OFF on xStocks)

`ReserveConfig.deleveragingMarginCallPeriodSecs` and `deleveragingThresholdDecreaseBpsPerDay` (`idl/kamino/klend.json:7813-7828`) describe the auto-deleverage mechanism: when `autodeleverage_enabled = 1` and a reserve crosses its deposit cap, Kamino can begin a slow margin-call cascade that gradually decreases the effective liquidation threshold, forcing graduated unwinding before a full liquidation event.

**On all 8 xStock reserves at snapshot, `autodeleverage_enabled = 0`.** The mechanism exists in the IDL but is disabled here. There is no soft-liquidation path, no graduated wind-down, no margin-call pre-stage on xStocks: the obligation either passes the health check or is liquidatable at the next Scope read.

### 4.4 Closed-market deferral (implicit, not explicit)

The xStocks lending market has no explicit "weekend mode," no `market_status`-gated branch, and no time-based deferral. Closed-market protection is **emergent** from three implicit gates:

1. **Scope's stale-held value during weekends** — if the underlying price didn't move on Scope's view, the LTV doesn't change, and no health threshold is crossed. (Documented in `docs/sources/oracles/scope.md` §3.)
2. **TWAP divergence rejection** at 5% — a sudden re-price on Monday open that exceeds 5% vs. the (stale-held) TWAP would *block* the price read, deferring liquidation by program design rather than by intention.
3. **PriceHeuristic guard rail** — large weekend dislocations could fall outside the static `[lower, upper]` range (especially QQQx and AAPLx; see §1.4), again blocking the operation.

The protocol's net behavior during a large adverse weekend move is **"block, don't liquidate, defer until prices look sane again"** — which sounds protective but loses information: borrowers and liquidators alike are frozen out, the bad-debt position widens silently, and the reserve absorbs the residual when normal operations resume. Paper 3's policy comparison must distinguish "served band would have liquidated earlier" from "served band would have averted the block-state altogether."

---

## 5. Empirical event rate (the "zero events" finding)

Per `reports/kamino_liquidations_first_scan.md`: **zero liquidation events in the 30-day window 2026-03-28 → 2026-04-27 across all 8 xStock reserves.** 1,146 signatures scanned; both `liquidate_obligation_and_redeem_reserve_collateral` (V1) and `_v2` discriminators verified; the zero is genuine.

Three plausible causes (the report's analysis):

1. **Low borrow utilization on xStock collateral** — the borrow limits on GOOGLx, AAPLx, MSTRx, HOODx are 0 (deposit-only); SPYx has a 5,000-token cap; the active-borrow book is small.
2. **No realized adverse moves large enough to breach the LTV gaps** — recent weekends (per `reports/kamino_xstocks_weekend_*`.md scoring) have been comfortably inside the buffer.
3. **Dynamic-bonus economics make small near-threshold liquidations unprofitable** for solo bots when net-of-protocol-fee bonus is ~2.5% on small positions.

For Paper 3, the operational consequence is: **the empirical event panel for "did soothsayer's band change a real liquidation outcome?" cannot be built on Kamino-xStocks alone.** Either (a) extend the historical window back to 2025-07-14 launch, (b) extend the protocol surface to MarginFi (load-bearing per `docs/sources/lending/marginfi.md`), or (c) frame Paper 3 as forward-looking scenario analysis. The recommended order is all three.

---

## 6. Open questions and gaps

1. **The dynamic-bonus curve `curve(health)` is not surfaced in the IDL or snapshot.** Likely deterministic in program logic — read `programs/klend/src/state/reserve.rs` or equivalent in the Kamino source if/when published; otherwise empirical reconstruction from the (sparse) on-chain liquidation events on non-xStock reserves is the fallback. Gating: Kamino governance / GitHub source if open; otherwise empirical fit on liquidation events from `kamino/liquidations/v1` once it lands in scryer.
2. **The "0.1% median liquidation penalty since September 2025" figure** in `reports/kamino_liquidations_first_scan.md:53` does not match the `[5%, 10%]` `[min, max]` range in the xStocks-reserves snapshot. Most likely it refers to a different Kamino product surface (Multiply / vaults / soft-liquidations on other markets) — needs clarification before being cited in Paper 3.
3. **Soft-liquidation behavior is documented in Kamino marketing but is disabled on xStocks** (`autodeleverage_enabled = 0`). Whether xStocks would ever turn this on, and what the trigger condition would be, is a governance question.
4. **The PriceHeuristic governance update cadence** — when does `[lower, upper]` get adjusted? If a heuristic upper bound is breached during a real adverse move, the operation blocks until governance updates the bound. The cadence and process are not pinned. (Critical for QQQx and AAPLx given the tight upper headroom in §1.4.)
5. **Whether the dynamic bonus is a function of current health, time-since-trigger, or both.** Different protocols implement different curves; Kamino's specific function is the unknown.
6. **Per-reserve historical bonus payouts** — empirical reconstruction of where in `[5%, 10%]` actual bonuses landed in past liquidations. Gating: `kamino/liquidations/v1` scryer dataset (already in scryer/wishlist Priority-0 #1).
7. **The Scope `OraclePrices` writer identity and update authority** — `oracles/scope.md` §6 has the open question; relevant here because a single writer is the single point of failure for all 8 reserves.

---

## 7. References

- On-chain reserve config: `data/processed/kamino_xstocks_snapshot_20260427.json` (8 reserves, full ReserveConfig + TokenInfo decoded).
- Klend IDL: `idl/kamino/klend.json` v1.19.0 — `ReserveConfig` struct at lines 7685–7878.
- Scope IDL: `idl/kamino/scope.json` v0.33.0 — `OraclePrices` and `DatedPrice` at lines 153–173 and 1658–1686.
- Per-venue oracle methodology: `docs/sources/oracles/scope.md` (the Sunday-stale-hold finding, the single-PDA exposure).
- Liquidation event scan: `reports/kamino_liquidations_first_scan.md` (zero-events, 30 days).
- Forward-running comparator (uses these parameters today): `reports/kamino_xstocks_weekend_20260424.md`, `reports/kamino_xstocks_weekend_20260417.md`.
- The stylized demo ladder this file supersedes: `crates/soothsayer-demo-kamino/src/lib.rs`.
- Roadmap requirement this file closes: `docs/ROADMAP.md` §"Must fix before Paper 3 is credible" #1 (verified end-to-end action semantics).
