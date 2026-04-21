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
XSTOCK_FEEDS: dict[str, str] = {
    "000ac6ba1b453a15ddf5fa59f28e9b32f49be3c65d3e3ad52eadd06ac1ef2a77": "SPYx",
    "000a1db22e3e1aa6a4478d8bff1b2e4b17d14a7ed1b5cb5de3b7dcd68eaef267": "QQQx",
    "000a80c655069b61d168b887d5e7f4231fe288c6ccb84b1854c9ccead20f3398": "TSLAx",
    "000a724ccab2a88597a6edda02eb0b12c0e07e05b22b35a6e55f2d12e5110054": "GOOGLx",
    "000a7a12270b5a3065be9b88a61fb09e7ad5aa10abd38eac30432cb1a0f8452b": "AAPLx",
    "000a9811a9bef7347f31f94c3f93c925a25f2b1f1ad11e1cd2b77e0cee151baa": "NVDAx",
    "000a7b26938f7df820f6fac6bce87b16a6d32d82a8c3213ab4d41bdc03536255": "MSTRx",
    "000a234978169682ac39ee0c19ffbd5a61a52ecb09b5f44a37d6d7be4f8020fe": "HOODx",
}


def feed_id_to_xstock(feed_id: bytes | str) -> str | None:
    """Return the xStock symbol for a known feedId, or None if unrecognised."""
    if isinstance(feed_id, bytes):
        feed_id = feed_id.hex()
    return XSTOCK_FEEDS.get(feed_id.lower().removeprefix("0x"))


def xstock_feed_ids_bytes() -> dict[str, bytes]:
    """Return {symbol: feed_id_bytes} for the 8 xStocks."""
    return {sym: bytes.fromhex(fid) for fid, sym in XSTOCK_FEEDS.items()}
