"""Snapshot live Kamino xStock reserve configs to a versioned JSON artifact.

Phase 1 Week 3 / Step 1 of the real-data Kamino comparator. Replaces the
``kamino_deviation_bps = 300`` placeholder in
``crates/soothsayer-demo-kamino/src/bin/run_demo.rs`` with the actual on-chain
reserve parameters that Kamino publishes for each xStock collateral.

What this captures per (xStock symbol → Reserve PDA):

- ``loanToValuePct`` (max LTV at origination)
- ``liquidationThresholdPct`` (LTV at which liquidation fires)
- ``borrowFactorPct`` (debt-side risk weight)
- ``minLiquidationBonusBps`` / ``maxLiquidationBonusBps`` / ``badDebtLiquidationBonusBps``
- ``tokenInfo.heuristic`` — Kamino's on-chain price-validity guard rail
  ``[lower, upper]`` at exponent ``exp``. Scope reads outside this band are
  rejected. This is the closest thing to an incumbent "band" that Kamino
  publishes; everything else is a point-plus-LTV-margin construction.
- ``tokenInfo.scopeConfiguration`` — Scope feed PDA and price chain that
  Kamino consumes. We need these PDAs in Step 2 (forward-running tape) to
  observe Kamino's actually-served price each weekend.
- ``tokenInfo.pythConfiguration`` / ``switchboardConfiguration`` — fallback
  oracle wiring. For all xStocks today these are zeroed (system-program
  sentinel), confirming Scope is the active path.
- ``tokenInfo.maxAgePriceSeconds`` — Kamino's staleness cutoff.

Output: ``data/processed/kamino_xstocks_snapshot_YYYYMMDD.json`` (versioned by
date so historical config can be diffed across snapshots if Kamino governance
mutates a parameter).

Run:
    uv run python scripts/snapshot_kamino_xstocks.py

Free-tier reads only. Uses the existing Helius RPC client at
``src/soothsayer/sources/helius.py``.
"""
from __future__ import annotations

import base64
import json
from datetime import date
from pathlib import Path

from anchorpy import Idl
from anchorpy.coder.accounts import AccountsCoder

from soothsayer.config import DATA_PROCESSED, REPO_ROOT
from soothsayer.sources.helius import rpc
from soothsayer.sources.jupiter import XSTOCK_MINTS

KLEND_PROGRAM = "KLend2g3cP87fffoy8q1mQqGKjrxjC8boSyAYavgmjD"
KLEND_IDL_PATH = REPO_ROOT / "idl" / "kamino" / "klend.json"

# Reserve account layout offsets (after the 8-byte Anchor discriminator):
# 0..8    discriminator
# 8..16   version (u64)
# 16..32  lastUpdate (16 bytes)
# 32..64  lendingMarket (Pubkey)
# 64..96  farmCollateral (Pubkey)
# 96..128 farmDebt (Pubkey)
# 128..   liquidity.mintPubkey (Pubkey)  ← memcmp filter target
LIQUIDITY_MINT_OFFSET = 128

# Solana system-program "null sentinel" — Kamino zeros oracle slots they don't use.
NULL_PUBKEY = "11111111111111111111111111111111"


def find_xstock_reserves(coder: AccountsCoder) -> list[dict]:
    """Locate every Kamino reserve whose `liquidity.mintPubkey` matches one of
    our xStock mints. A given mint may appear in multiple lending markets
    (Main, Jito, xStocks, ...); we record all matches and the lendingMarket
    each one belongs to.
    """
    rows: list[dict] = []
    for symbol, mint in XSTOCK_MINTS.items():
        # Stage 1: list reserves with this mint, no body.
        result = rpc("getProgramAccounts", [
            KLEND_PROGRAM,
            {
                "encoding": "base64",
                "filters": [
                    {"memcmp": {"offset": LIQUIDITY_MINT_OFFSET, "bytes": mint}},
                ],
                "dataSlice": {"offset": 0, "length": 0},
            },
        ])
        if not result:
            print(f"  [{symbol}] no reserves found for mint {mint}")
            continue
        for entry in result:
            reserve_pda = entry["pubkey"]
            # Stage 2: fetch the full account body.
            full = rpc("getAccountInfo", [reserve_pda, {"encoding": "base64"}])
            if not full or not full.get("value"):
                print(f"  [{symbol}] reserve {reserve_pda}: empty getAccountInfo")
                continue
            data_b64 = full["value"]["data"][0]
            raw = base64.b64decode(data_b64)
            decoded = coder.parse(raw)
            d = decoded.data

            ti = d.config.token_info
            heuristic = ti.heuristic
            scope = ti.scope_configuration
            pyth = ti.pyth_configuration
            sb = ti.switchboard_configuration

            name_bytes = bytes(ti.name)
            name_str = name_bytes.split(b"\x00", 1)[0].decode("ascii", errors="replace").strip()

            # Resolve effective heuristic band into human prices: lower/upper
            # are stored as integers at exponent `exp`, where the on-chain
            # convention is real_price = stored / 10^exp. (Same convention as
            # the Soothsayer wire format in `state::PriceHeuristic`.)
            exp = int(heuristic.exp)
            scale = 10 ** exp if exp > 0 else 1
            heuristic_lower_real = heuristic.lower / scale if exp > 0 else float(heuristic.lower)
            heuristic_upper_real = heuristic.upper / scale if exp > 0 else float(heuristic.upper)

            row = {
                "symbol": symbol,
                "mint": mint,
                "reserve_pda": reserve_pda,
                "lending_market": str(d.lending_market),
                "liquidity_mint_decimals": int(d.liquidity.mint_decimals),
                "config": {
                    "status": int(d.config.status),
                    "emergency_mode": int(d.config.emergency_mode),
                    "loan_to_value_pct": int(d.config.loan_to_value_pct),
                    "liquidation_threshold_pct": int(d.config.liquidation_threshold_pct),
                    "borrow_factor_pct": int(d.config.borrow_factor_pct),
                    "min_liquidation_bonus_bps": int(d.config.min_liquidation_bonus_bps),
                    "max_liquidation_bonus_bps": int(d.config.max_liquidation_bonus_bps),
                    "bad_debt_liquidation_bonus_bps": int(d.config.bad_debt_liquidation_bonus_bps),
                    "protocol_liquidation_fee_pct": int(d.config.protocol_liquidation_fee_pct),
                    "protocol_take_rate_pct": int(d.config.protocol_take_rate_pct),
                    "deposit_limit": int(d.config.deposit_limit),
                    "borrow_limit": int(d.config.borrow_limit),
                    "block_borrowing_above_utilization_pct": int(
                        d.config.utilization_limit_block_borrowing_above_pct
                    ),
                    "autodeleverage_enabled": int(d.config.autodeleverage_enabled),
                    "block_ctoken_usage": int(d.config.block_ctoken_usage),
                    "disable_usage_as_coll_outside_emode": int(
                        d.config.disable_usage_as_coll_outside_emode
                    ),
                },
                "token_info": {
                    "name": name_str,
                    "max_age_price_seconds": int(ti.max_age_price_seconds),
                    "max_age_twap_seconds": int(ti.max_age_twap_seconds),
                    "max_twap_divergence_bps": int(ti.max_twap_divergence_bps),
                    "block_price_usage": int(ti.block_price_usage),
                    "heuristic": {
                        "lower_raw": int(heuristic.lower),
                        "upper_raw": int(heuristic.upper),
                        "exp": exp,
                        "lower_price": heuristic_lower_real,
                        "upper_price": heuristic_upper_real,
                    },
                    "scope": {
                        "price_feed": str(scope.price_feed),
                        "price_chain": [int(x) for x in scope.price_chain],
                        "twap_chain": [int(x) for x in scope.twap_chain],
                        "active": str(scope.price_feed) != NULL_PUBKEY,
                    },
                    "pyth": {
                        "price": str(pyth.price),
                        "active": str(pyth.price) != NULL_PUBKEY,
                    },
                    "switchboard": {
                        "price_aggregator": str(sb.price_aggregator),
                        "twap_aggregator": str(sb.twap_aggregator),
                        "active": str(sb.price_aggregator) != NULL_PUBKEY,
                    },
                },
            }
            rows.append(row)
            print(
                f"  [{symbol}] {reserve_pda}: market {row['lending_market'][:8]}…  "
                f"LTV={row['config']['loan_to_value_pct']}/{row['config']['liquidation_threshold_pct']}  "
                f"heuristic=[${row['token_info']['heuristic']['lower_price']:.2f}, "
                f"${row['token_info']['heuristic']['upper_price']:.2f}]  "
                f"oracle={'scope' if row['token_info']['scope']['active'] else 'none'}"
            )
    return rows


def main() -> None:
    if not KLEND_IDL_PATH.exists():
        raise SystemExit(
            f"klend IDL missing at {KLEND_IDL_PATH}. Refresh with:\n"
            f"  anchor idl fetch {KLEND_PROGRAM} --provider.cluster mainnet "
            f"> {KLEND_IDL_PATH}"
        )
    idl = Idl.from_json(KLEND_IDL_PATH.read_text())
    coder = AccountsCoder(idl)
    print(f"Loaded klend IDL v{idl.version} ({len(idl.accounts)} accounts, {len(idl.types)} types)")
    print(f"Scanning {len(XSTOCK_MINTS)} xStock mints under program {KLEND_PROGRAM}...")

    rows = find_xstock_reserves(coder)

    today = date.today().isoformat().replace("-", "")
    out_path: Path = DATA_PROCESSED / f"kamino_xstocks_snapshot_{today}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "snapshot_date": date.today().isoformat(),
        "klend_program": KLEND_PROGRAM,
        "klend_idl_version": idl.version,
        "n_reserves": len(rows),
        "reserves": rows,
    }
    with out_path.open("w") as f:
        json.dump(snapshot, f, indent=2, default=str)
    print(f"\nWrote {len(rows)} reserves → {out_path}")

    # Quick distribution summary.
    if rows:
        markets = {r["lending_market"] for r in rows}
        print(f"  Distinct lending markets: {len(markets)}")
        for m in sorted(markets):
            in_market = [r["symbol"] for r in rows if r["lending_market"] == m]
            print(f"    {m}: {len(in_market)} reserves ({', '.join(in_market)})")


if __name__ == "__main__":
    main()
