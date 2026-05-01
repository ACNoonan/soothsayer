# Kamino-Klend xStocks liquidation scan — first run

**Generated:** 2026-04-27 12:58 UTC  
**Script:** `scripts/scan_kamino_liquidations.py`  
**Window:** last 30 days (min_block_time = 1774702073, ~2026-03-28 → 2026-04-27)  
**Market:** `5wJeMrUYECGq41fxRESKALVcHnNX26TAWy4W98yULsua` (Kamino xStocks lending market)  
**Provider routing:** dual (Helius + RPC Fast); the default Helius pagination call hit 429 under daemon load, the rerun used `PRIMARY_RPC=rpcfast`.

## Headline result: zero liquidation events in 30 days

| Metric | Value |
|---|---:|
| Signatures scanned | 1,146 |
| Liquidation events decoded | **0** |
| Throughput | 1.8 sigs/s (RPC-throttled by daemon contention) |
| Scan duration | 623 s (~10 min) |

Discriminator detection verified by SHA-256 of the Anchor IX names:

```
liquidate_obligation_and_redeem_reserve_collateral     b1479abce2854a37  ← matches LIQUIDATE_V1_DISC
liquidate_obligation_and_redeem_reserve_collateral_v2  a2a1238f1ebbb967  ← matches LIQUIDATE_V2_DISC
```

The script walks both top-level and inner instructions and matches the leading 8 bytes against these. With both versions covered and 1,146 signatures processed, the zero-event finding is genuine — the xStocks Kamino market has not produced any liquidation IX in the last 30 days.

## Why this matters

This is a **material finding** for Paper 3 and for any future event-driven extension work, and it should be surfaced honestly.

**For any future event-driven empirical work:** the H₀-vs-H₁ test relies on a panel of liquidation events with measurable OEV. A 30-day window of zero events on Kamino-xStocks specifically means:

  - The empirical-replay claim cannot be substantiated on Kamino-xStocks alone over recent windows.
  - **MarginFi is now the load-bearing source of liquidation events** for any serious event-panel build, not Kamino.
  - The retrospective 3.56× dominance anchor was derived from underlier proxies (the 12-year Soothsayer panel), not from on-chain Solana liquidations. The on-chain replay still needs to be built; this scan suggests the historical window has to extend further back AND/OR widen across markets.

**For Paper 3** (`reports/paper3_liquidation_policy/plan.md`): the policy-comparison empirical work was scoped around xStocks-on-Kamino. With zero events in a 30-day window, the paper either:

  - Extends the empirical horizon to xStocks history since launch (2025-07-14, ~287 days back), OR
  - Extends the protocol surface to MarginFi / Drift / Save / Loopscale, OR
  - Acknowledges the policy comparison as forward-looking scenario analysis rather than retrospective empirical claim.

Most defensible: do all three, in that order.

## Why xStocks-on-Kamino has had zero recent liquidations

Three plausible explanations, ordered by my prior on each:

1. **Low borrow utilization on xStock collateral.** xStocks are a niche, post-mid-2025 asset class on Kamino. Most lenders may be supply-side only; the borrowing book against xStocks may simply be small enough that no positions have crossed the liquidation threshold.

2. **No realized adverse moves large enough to breach LTV gaps.** Per `data/processed/kamino_xstocks_snapshot_20260426.json`, SPYx and QQQx have a 2pp LTV-to-liquidation-threshold gap (origination 73% / 70%, liquidation 75% / 72%); the others sit at 10pp gaps. Recent weekend moves (per the v1 weekend-comparison scoring at `reports/kamino_xstocks_weekend_*.md`) have all been comfortably inside those gaps.

3. **Liquidator economics.** Kamino's median liquidation penalty dropped to 0.1% in September 2025. If any near-threshold positions did exist, the unprofitable median liquidation may have left them unliquidated by solo bots, with the protocol absorbing the residual rather than triggering an IX.

(1) and (2) are the dominant explanations under the Soothsayer prior; (3) explains why solo-liquidator economics make small-rent IXs unprofitable but doesn't fully explain the absolute zero.

## What a deeper scan would tell us

Three follow-up scans, ordered by information value per minute of scan time:

| Follow-up | Scope | ETA (RPC Fast) | Decisive of |
|---|---|---:|---|
| `--days-back 280` on xStocks Kamino | Full xStock history since launch (2025-07-14) | ~100 min | Whether xStocks have *ever* produced a liquidation event on Kamino |
| Same script vs MarginFi xStocks market | `scripts/snapshot_marginfi_xstocks.py` not yet built | ~2 hr to build + scan | Whether MarginFi (the grant's load-bearing protocol) has a usable event panel |
| Cross-protocol scan (Drift / Save / Loopscale) | Per-protocol IDL + reserve-config decoder | days | Grant's M2 stretch goal |

The first follow-up is the cheapest gate-closer — a single overnight run answers "is the empirical xStocks-on-Kamino panel literally empty since launch, or just empty in recent windows?". My prior is the panel is non-empty over the full 280 days but small (<50 events).

## Files produced

  - `data/processed/kamino_liquidations.parquet` — 0-row consolidated panel
  - `data/processed/kamino_liquidations_events.jsonl` — 0-row append-only events log (will be populated by future scans)
  - `data/processed/kamino_liquidations_checkpoint.json` — pagination checkpoint, valid for `--resume`
  - `data/processed/kamino_liquidations.summary.json` — this scan's summary (zero counts)

All four are gitignored under `data/processed/*`; the script + this report are the durable artifacts. Re-run with `--resume` to pick up where this scan left off, or `--reset` to start fresh.

## Recommendation

For the launchd Monday rollup landing in ~90 minutes — no change. The rollup doesn't depend on this scan. The first live weekend report will land on schedule and surface the new Pyth-as-fifth-method comparator alongside Soothsayer / Kamino-incumbent / simple heuristic for the 2026-04-24 → 2026-04-27 weekend.

For the grant + Paper 3 — defer the deep-history scan until daemons can be paused (12-15 min of dual-provider Helius would crush 280 days of signatures), or run it overnight on RPC Fast. The result either confirms the xStocks-on-Kamino panel is too thin for the grant's empirical work (in which case the grant pivot to MarginFi is load-bearing), or surfaces a small but non-zero historical panel (in which case the original framing holds, just with a smaller-N empirical anchor than implied).
