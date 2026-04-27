"""Snapshot every borrower obligation in Kamino's xStocks lending market.

Phase 1 publication-risk gate: Paper 3 §"book priors". Until now, expected-loss
claims rely on synthetic borrower books. This script extracts the *actual*
distribution of where borrowers sit relative to liquidation thresholds in the
deployed xStocks market, so Paper 3 can anchor:

- per-reserve utilization (count of obligations / total deposit value / total
  borrow value),
- effective-LTV distribution (borrow_factor_adjusted_debt / deposited_value),
- distance-to-liquidation distribution (1 - bf_debt / unhealthy_borrow_value),
- concentration (share of book held by top-N obligations, share of fragile
  obligations concentrated in any one collateral).

Reads the reserve snapshot at ``data/processed/kamino_xstocks_snapshot_*.json``
to map reserve PDAs back to symbols. The market we scan is hard-coded to the
xStocks market id captured in that snapshot — same market every reserve in our
snapshot lives in.

Output: ``data/processed/kamino_obligations_snapshot_YYYYMMDD.json``
(versioned by date so book-prior drift can be tracked over time).

Run:
    uv run python scripts/snapshot_kamino_obligations.py

Free-tier reads only. Single ``getProgramAccounts`` call (one round-trip),
plus N=0 follow-ups — the obligation account body fits in the bulk response.
"""
from __future__ import annotations

import argparse
import base64
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from statistics import median

import base58
from anchorpy import Idl
from anchorpy.coder.accounts import AccountsCoder

from soothsayer.config import DATA_PROCESSED, REPO_ROOT
from soothsayer.sources.helius import rpc

KLEND_PROGRAM = "KLend2g3cP87fffoy8q1mQqGKjrxjC8boSyAYavgmjD"
KLEND_IDL_PATH = REPO_ROOT / "idl" / "kamino" / "klend.json"

# Obligation account layout offsets (after the 8-byte Anchor discriminator):
# 0..8     discriminator                         ← memcmp #1
# 8..16    tag (u64)
# 16..32   lastUpdate (16 bytes: slot + flags)
# 32..64   lendingMarket (Pubkey)                ← memcmp #2
# 64..96   owner (Pubkey)
# 96..     deposits[8] of ObligationCollateral
# ...
LENDING_MARKET_OFFSET = 32

# Kamino's scaled-fraction convention is 60 fractional bits (per IDL docstring
# at klend.json:8023 — "scaled fraction (60 bits fractional part)"). Every
# `*_sf` field in the obligation is a u128 with this scale.
SF_DIVISOR = 1 << 60

# System-program / default pubkey sentinel — Kamino zeroes unused slots in the
# fixed-size deposits[8] / borrows[5] arrays.
NULL_PUBKEY = "11111111111111111111111111111111"


def _sf_to_float(x: int) -> float:
    return float(x) / SF_DIVISOR


def _load_reserve_map() -> tuple[str, dict[str, dict]]:
    """Return (xstocks_market_pda, {reserve_pda: {symbol, ltv, liq, decimals}})
    from the latest reserve snapshot.
    """
    candidates = sorted(
        DATA_PROCESSED.glob("kamino_xstocks_snapshot_*.json"),
        reverse=True,
    )
    if not candidates:
        raise SystemExit(
            "No reserve snapshot found. Run scripts/snapshot_kamino_xstocks.py first."
        )
    snap = json.loads(candidates[0].read_text())
    market_pdas = {r["lending_market"] for r in snap["reserves"]}
    if len(market_pdas) != 1:
        raise SystemExit(
            f"Expected all xStock reserves in one lending market; got {len(market_pdas)}: "
            f"{market_pdas}"
        )
    market_pda = next(iter(market_pdas))
    reserve_map = {
        r["reserve_pda"]: {
            "symbol": r["symbol"],
            "ltv": r["config"]["loan_to_value_pct"],
            "liq": r["config"]["liquidation_threshold_pct"],
            "decimals": r["liquidity_mint_decimals"],
        }
        for r in snap["reserves"]
    }
    return market_pda, reserve_map


def _fetch_obligations(coder: AccountsCoder, market_pda: str) -> list[dict]:
    """Pull every obligation in the given lending market via getProgramAccounts.

    Two memcmp filters: account discriminator (so non-Obligation accounts are
    excluded server-side) and lendingMarket (so only this market's obligations
    return). The response includes the full account body — no follow-up
    getAccountInfo needed.
    """
    obligation_disc = coder.acc_name_to_discriminator["Obligation"]
    disc_b58 = base58.b58encode(obligation_disc).decode()

    print(f"getProgramAccounts {KLEND_PROGRAM} (market {market_pda[:8]}…)…")
    result = rpc(
        "getProgramAccounts",
        [
            KLEND_PROGRAM,
            {
                "encoding": "base64",
                "filters": [
                    {"memcmp": {"offset": 0, "bytes": disc_b58}},
                    {"memcmp": {"offset": LENDING_MARKET_OFFSET, "bytes": market_pda}},
                ],
            },
        ],
    )
    if not result:
        return []

    rows: list[dict] = []
    for entry in result:
        pda = entry["pubkey"]
        data_b64 = entry["account"]["data"][0]
        raw = base64.b64decode(data_b64)
        try:
            decoded = coder.parse(raw).data
        except Exception as e:
            print(f"  [{pda}] decode failed: {type(e).__name__}: {e}")
            continue

        deposits: list[dict] = []
        for c in decoded.deposits:
            reserve = str(c.deposit_reserve)
            if reserve == NULL_PUBKEY:
                continue
            deposits.append(
                {
                    "deposit_reserve": reserve,
                    "deposited_amount": int(c.deposited_amount),
                    "market_value_usd": _sf_to_float(int(c.market_value_sf)),
                }
            )

        borrows: list[dict] = []
        for b in decoded.borrows:
            reserve = str(b.borrow_reserve)
            if reserve == NULL_PUBKEY:
                continue
            borrows.append(
                {
                    "borrow_reserve": reserve,
                    "borrowed_amount_sf": int(b.borrowed_amount_sf),
                    "market_value_usd": _sf_to_float(int(b.market_value_sf)),
                    "bf_adjusted_value_usd": _sf_to_float(
                        int(b.borrow_factor_adjusted_market_value_sf)
                    ),
                }
            )

        deposited_value = _sf_to_float(int(decoded.deposited_value_sf))
        bf_adjusted_debt = _sf_to_float(int(decoded.borrow_factor_adjusted_debt_value_sf))
        borrowed_assets = _sf_to_float(int(decoded.borrowed_assets_market_value_sf))
        allowed_borrow = _sf_to_float(int(decoded.allowed_borrow_value_sf))
        unhealthy_borrow = _sf_to_float(int(decoded.unhealthy_borrow_value_sf))

        # Effective LTV is the metric Kamino's trigger uses: bf-adjusted debt
        # divided by deposited value. Liquidation fires when this crosses the
        # weighted liquidation threshold (encoded as `unhealthy_borrow_value`).
        eff_ltv = bf_adjusted_debt / deposited_value if deposited_value > 0 else 0.0

        # Distance to liquidation in "value space": positive if healthy,
        # negative if liquidatable. Normalised by unhealthy_borrow_value so it
        # is comparable across obligation sizes.
        dist_to_liq_pp = (
            (unhealthy_borrow - bf_adjusted_debt) / unhealthy_borrow * 100
            if unhealthy_borrow > 0
            else float("inf")
        )

        rows.append(
            {
                "obligation_pda": pda,
                "owner": str(decoded.owner),
                "elevation_group": int(decoded.elevation_group),
                "has_debt": int(decoded.has_debt),
                "borrowing_disabled": int(decoded.borrowing_disabled),
                "lowest_reserve_max_ltv_pct": int(decoded.lowest_reserve_deposit_max_ltv_pct),
                "lowest_reserve_liq_ltv_pct": int(decoded.lowest_reserve_deposit_liquidation_ltv),
                "deposited_value_usd": deposited_value,
                "borrowed_assets_market_value_usd": borrowed_assets,
                "bf_adjusted_debt_usd": bf_adjusted_debt,
                "allowed_borrow_value_usd": allowed_borrow,
                "unhealthy_borrow_value_usd": unhealthy_borrow,
                "effective_ltv": eff_ltv,
                "distance_to_liq_pp": dist_to_liq_pp,
                "deposits": deposits,
                "borrows": borrows,
            }
        )

    return rows


def _percentiles(values: list[float], ps: list[int]) -> dict[str, float]:
    """Simple linear-interpolation percentiles. Empty input → all NaN."""
    if not values:
        return {f"p{p}": float("nan") for p in ps}
    s = sorted(values)
    n = len(s)
    out: dict[str, float] = {}
    for p in ps:
        if n == 1:
            out[f"p{p}"] = s[0]
            continue
        idx = (p / 100) * (n - 1)
        lo = int(idx)
        hi = min(lo + 1, n - 1)
        frac = idx - lo
        out[f"p{p}"] = s[lo] * (1 - frac) + s[hi] * frac
    return out


def _summarize(
    obligations: list[dict],
    reserve_map: dict[str, dict],
) -> dict:
    """Aggregate the obligation panel into the book-prior table Paper 3 needs."""
    n_total = len(obligations)
    with_debt = [o for o in obligations if o["bf_adjusted_debt_usd"] > 1e-6]
    n_with_debt = len(with_debt)

    # --- Per-reserve usage (count of obligations touching each reserve, total
    # value on each side). Reports both sides per reserve PDA.
    deposit_counts: Counter[str] = Counter()
    deposit_value: defaultdict[str, float] = defaultdict(float)
    borrow_counts: Counter[str] = Counter()
    borrow_value: defaultdict[str, float] = defaultdict(float)
    for o in obligations:
        for d in o["deposits"]:
            r = d["deposit_reserve"]
            deposit_counts[r] += 1
            deposit_value[r] += d["market_value_usd"]
        for b in o["borrows"]:
            r = b["borrow_reserve"]
            borrow_counts[r] += 1
            borrow_value[r] += b["market_value_usd"]

    # Union of all reserve PDAs we observed. Some may be non-xStock reserves
    # (e.g. USDC borrow legs in this market); we surface those too with a
    # symbol of "?" so the reader can see the full book composition.
    all_reserves = set(deposit_counts) | set(borrow_counts)
    per_reserve = []
    for r in sorted(all_reserves):
        meta = reserve_map.get(r, {})
        per_reserve.append(
            {
                "reserve_pda": r,
                "symbol": meta.get("symbol", "?"),
                "max_ltv_pct": meta.get("ltv"),
                "liq_threshold_pct": meta.get("liq"),
                "n_deposit_positions": deposit_counts[r],
                "deposit_value_usd": deposit_value[r],
                "n_borrow_positions": borrow_counts[r],
                "borrow_value_usd": borrow_value[r],
            }
        )

    # --- Effective-LTV histogram (debt-bearing obligations only). Bins in
    # 10pp steps from 0% to 100%, with a final 100%+ overflow bin for
    # technically-liquidatable obligations the keeper hasn't picked off yet.
    ltv_bins_edges = [(i, i + 10) for i in range(0, 100, 10)]
    ltv_hist: dict[str, int] = {f"{lo}-{hi}%": 0 for lo, hi in ltv_bins_edges}
    ltv_hist["100%+"] = 0
    for o in with_debt:
        pct = o["effective_ltv"] * 100
        placed = False
        for lo, hi in ltv_bins_edges:
            if lo <= pct < hi:
                ltv_hist[f"{lo}-{hi}%"] += 1
                placed = True
                break
        if not placed:
            ltv_hist["100%+"] += 1

    # --- Distance-to-liquidation tail. Reports how many debt-bearing
    # obligations sit within {1, 2, 5, 10}pp of the unhealthy-borrow trigger.
    # These are the borrowers a weekend gap could push into liquidation.
    dists = sorted(o["distance_to_liq_pp"] for o in with_debt)
    fragility = {
        "n_within_0pp_already_liquidatable": sum(1 for d in dists if d < 0),
        "n_within_1pp": sum(1 for d in dists if 0 <= d < 1),
        "n_within_2pp": sum(1 for d in dists if 0 <= d < 2),
        "n_within_5pp": sum(1 for d in dists if 0 <= d < 5),
        "n_within_10pp": sum(1 for d in dists if 0 <= d < 10),
    }

    # --- Concentration: top-10 obligations by deposit value, share of book
    # held by top-K, and which collateral symbol dominates in fragile
    # obligations (within 5pp of liquidation).
    by_size = sorted(obligations, key=lambda o: -o["deposited_value_usd"])
    total_dep = sum(o["deposited_value_usd"] for o in obligations) or 1.0
    top10_share = sum(o["deposited_value_usd"] for o in by_size[:10]) / total_dep
    top1_share = by_size[0]["deposited_value_usd"] / total_dep if by_size else 0.0

    fragile_collateral_counter: Counter[str] = Counter()
    fragile = [o for o in with_debt if 0 <= o["distance_to_liq_pp"] < 5]
    for o in fragile:
        # Attribute fragility to the largest deposited xStock collateral in
        # the obligation. Non-xStock deposits are surfaced as "?" so the
        # reader can see how often fragility traces back to USDC etc.
        if not o["deposits"]:
            continue
        biggest = max(o["deposits"], key=lambda d: d["market_value_usd"])
        sym = reserve_map.get(biggest["deposit_reserve"], {}).get("symbol", "?")
        fragile_collateral_counter[sym] += 1

    return {
        "n_obligations_total": n_total,
        "n_obligations_with_debt": n_with_debt,
        "n_obligations_empty": n_total - n_with_debt,
        "total_deposited_value_usd": total_dep if total_dep > 1.0 else 0.0,
        "total_borrowed_value_usd": sum(o["borrowed_assets_market_value_usd"] for o in obligations),
        "total_bf_adjusted_debt_usd": sum(o["bf_adjusted_debt_usd"] for o in with_debt),
        "per_reserve": per_reserve,
        "effective_ltv_histogram": ltv_hist,
        "effective_ltv_percentiles": _percentiles(
            [o["effective_ltv"] for o in with_debt], [10, 25, 50, 75, 90, 95, 99]
        ),
        "distance_to_liq_pp_percentiles": _percentiles(
            [o["distance_to_liq_pp"] for o in with_debt], [1, 5, 10, 25, 50, 75, 90]
        ),
        "fragility_counts": fragility,
        "concentration": {
            "top1_share_of_deposits": top1_share,
            "top10_share_of_deposits": top10_share,
            "fragile_obligations_by_dominant_collateral": dict(fragile_collateral_counter),
        },
    }


def _print_human_summary(market_pda: str, summary: dict, reserve_map: dict[str, dict]) -> None:
    print(f"\nxStocks market {market_pda}")
    print(f"  obligations:  total={summary['n_obligations_total']}, "
          f"with_debt={summary['n_obligations_with_debt']}, "
          f"empty={summary['n_obligations_empty']}")
    print(f"  deposits ${summary['total_deposited_value_usd']:,.0f}  "
          f"borrows ${summary['total_borrowed_value_usd']:,.0f}  "
          f"bf-adj debt ${summary['total_bf_adjusted_debt_usd']:,.0f}")

    print("\n  per-reserve:")
    for r in summary["per_reserve"]:
        sym = r["symbol"]
        print(f"    {sym:>6}  {r['reserve_pda'][:8]}…  "
              f"deps {r['n_deposit_positions']:>4} (${r['deposit_value_usd']:>14,.0f})  "
              f"borrows {r['n_borrow_positions']:>4} (${r['borrow_value_usd']:>14,.0f})")

    print("\n  effective-LTV histogram (debt-bearing only):")
    for bucket, n in summary["effective_ltv_histogram"].items():
        if n:
            print(f"    {bucket:>10}: {n}")

    p = summary["effective_ltv_percentiles"]
    print(f"\n  effective-LTV percentiles: p50={p['p50']:.3f}  p75={p['p75']:.3f}  "
          f"p90={p['p90']:.3f}  p95={p['p95']:.3f}  p99={p['p99']:.3f}")

    f = summary["fragility_counts"]
    print(f"\n  near-trigger borrowers: <0pp(already liquidatable)={f['n_within_0pp_already_liquidatable']}  "
          f"<1pp={f['n_within_1pp']}  <2pp={f['n_within_2pp']}  "
          f"<5pp={f['n_within_5pp']}  <10pp={f['n_within_10pp']}")

    c = summary["concentration"]
    print(f"\n  concentration: top1={c['top1_share_of_deposits']:.1%}  "
          f"top10={c['top10_share_of_deposits']:.1%}")
    if c["fragile_obligations_by_dominant_collateral"]:
        items = sorted(c["fragile_obligations_by_dominant_collateral"].items(),
                       key=lambda kv: -kv[1])
        print(f"  fragile obligations by dominant collateral: "
              f"{', '.join(f'{s}={n}' for s, n in items)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Override output path (default: data/processed/kamino_obligations_snapshot_YYYYMMDD.json)",
    )
    args = parser.parse_args()

    if not KLEND_IDL_PATH.exists():
        raise SystemExit(f"klend IDL missing at {KLEND_IDL_PATH}")
    idl = Idl.from_json(KLEND_IDL_PATH.read_text())
    coder = AccountsCoder(idl)

    market_pda, reserve_map = _load_reserve_map()
    print(f"Loaded klend IDL v{idl.version}; reserve map: {len(reserve_map)} xStock reserves "
          f"in market {market_pda[:8]}…")

    obligations = _fetch_obligations(coder, market_pda)
    print(f"Decoded {len(obligations)} obligations")

    summary = _summarize(obligations, reserve_map)
    _print_human_summary(market_pda, summary, reserve_map)

    today = date.today().isoformat().replace("-", "")
    out_path = args.out or (DATA_PROCESSED / f"kamino_obligations_snapshot_{today}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "snapshot_date": date.today().isoformat(),
        "klend_program": KLEND_PROGRAM,
        "klend_idl_version": idl.version,
        "lending_market": market_pda,
        "summary": summary,
        "obligations": obligations,
    }
    with out_path.open("w") as f:
        json.dump(payload, f, indent=2, default=str)
    print(f"\nWrote {len(obligations)} obligations → {out_path}")


if __name__ == "__main__":
    main()
