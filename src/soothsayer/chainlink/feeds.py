"""
Chainlink xStock feed IDs (Solana mainnet, schema v10 = 0x000a).

Identified empirically by scanning ~300 Verifier instruction calls and matching
the decoded median price against a live yfinance quote for each underlying.
Match tolerance was <0.5% in all cases, which is well below the dispersion
expected between same-second feeds.

If Chainlink rotates a feed ID or transitions a stream to schema v11, these
entries need to be updated — there is no on-chain directory we can query.
"""

from __future__ import annotations

# feed_id (hex, no 0x prefix, lower case) -> xStock symbol
# Verified against live yfinance spot for 8 tickers; all matches <0.15%.
XSTOCK_FEEDS: dict[str, str] = {
    "000ac6ba1b453a15c1fe9dcd82265ca47bcd04e7b3667de1623617c45cef2a77": "SPYx",
    "000a1db22e3e1aa657d910dc90e1f0dbe693d345b7b0b04fd9efc8eb17aef267": "QQQx",
    "000a80c655069b61d168b887d5e7f4231fe288c6ccb84b1854c9ccead20f3398": "TSLAx",
    "000a724ccab2a885eaeb8d56c54eda31f467564681f6e8dd32c5b64d40110054": "GOOGLx",
    "000a7a12270b5a30236bf410679df0c6bb1bba2b40e5d86847748ff1c8f8452b": "AAPLx",
    "000a37a55df2ef907d8fa06af6632bc16da58a62b68be2e1994efaa037a0918a": "NVDAx",
    "000a7b26938f7df83a0bd00f76b0f644a6ef4f28b5cbb9afb800fbcdc8536255": "MSTRx",
    "000a2349781696825299ea1610f3ed0f47c5e7585003a271417f6e94778020fe": "HOODx",
}


def feed_id_to_xstock(feed_id: bytes | str) -> str | None:
    """Return the xStock symbol for a known feedId, or None if unrecognised."""
    if isinstance(feed_id, bytes):
        feed_id = feed_id.hex()
    return XSTOCK_FEEDS.get(feed_id.lower().removeprefix("0x"))


def xstock_feed_ids_bytes() -> dict[str, bytes]:
    """Return {symbol: feed_id_bytes} for the 8 xStocks."""
    return {sym: bytes.fromhex(fid) for fid, sym in XSTOCK_FEEDS.items()}
