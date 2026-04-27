"""
Chainlink xStock feed IDs (Solana mainnet).

This module exposes two registries — one per schema:

  - ``XSTOCK_FEEDS``      — schema v10 = 0x000a (Tokenized Asset, the
                           original xStock format).
  - ``XSTOCK_V11_FEEDS``  — schema v11 = 0x000b (RWA Advanced, distinct
                           feed IDs from v10).

Both were identified empirically by price-band correlation against
yfinance — see ``scripts/enumerate_v11_xstock_feeds.py`` and the
verifier-tx scans in ``scripts/scan_chainlink_schemas.py`` /
``scripts/verify_v11_cadence.py``. If Chainlink migrates a feed ID or
transitions a stream to a different schema, these entries need to be
updated — there is no on-chain directory we can query.

Schema note: v10 on Solana is Chainlink's "Tokenized Asset" schema
(13 words, 416 bytes) — it carries ``price``, ``tokenizedPrice``,
``marketStatus``, and corporate-action multipliers, but no bid/ask or
order book depth. v11 is an entirely different schema ("RWA Advanced")
that *does* carry ``bid`` / ``ask`` / ``mid`` / ``last_traded_price`` +
a finer 6-state ``marketStatus`` code set. See ``v10.py`` and ``v11.py``
for the exact layouts.
"""

from __future__ import annotations

# feed_id (hex, no 0x prefix, lower case) -> xStock symbol — Schema v10 (0x000a)
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

# Canonical v11 xStock feed IDs — schema 0x000b. Real-quote-preferred where
# alternate feeds exist for the same underlier (i.e., when both a real-quote
# and a placeholder-only v11 feed exist for the same xStock, the real-quote
# one is the canonical mapping).
#
# Identified empirically by ``scripts/enumerate_v11_xstock_feeds.py`` via
# price-band correlation: median ``last_traded_price`` per feed_id matched
# against yfinance Friday close for 2026-04-24, tolerance ±5%. Match
# precision sub-0.1% on all four entries. Real-quote vs placeholder
# classification confirmed by ``scripts/dump_v11_feed_inventory.py`` —
# real-quote feeds have 0% bid `.01`-suffix rate; placeholder feeds have
# 100%.
#
# Coverage gap: only 4 of 8 xStocks have observable v11 traffic in the
# 30000-Verifier-sig deep scan (~3-4 hours of recent traffic). AAPL, GOOGL,
# MSTR, HOOD did not surface v11 reports — either lower-frequency v11
# publishers, or v11 deployment for those underliers has not yet shipped.
# The Paper-1 §1.1 framing should remain qualified ("v11 weekend bid/ask
# placeholders observed for the v11 xStock feed IDs we have enumerated")
# rather than implying a universal v11 claim across all 8 xStocks.
XSTOCK_V11_FEEDS: dict[str, str] = {
    # SPYx / QQQx — only placeholder-shaped v11 feeds exist for these in our
    # 30k-sig scan window. The canonical mapping IS the placeholder feed.
    "000b0580ced23f9ae7fd77f817ad7e6aec23a04314454365cfe93060a9041bd3": "SPYx",
    "000b59dc1b9fb4305d750e501974eb6616c39d8c54f485bbb4f3d3ac3ce7dc91": "QQQx",
    # NVDAx / TSLAx — both have a real-quote AND a placeholder v11 feed.
    # Canonical mapping is the real-quote one (0% bid `.01`-suffix rate).
    # The placeholder twin is in XSTOCK_V11_PLACEHOLDER_ALTERNATES below.
    "000b6aa036224454037bab103184565f6aa9ea589c3b349f6d8471ee753524b9": "NVDAx",
    "000b2dbed1640ead18d37338b75e4755630a900649261baf4ed79d9a749be13d": "TSLAx",
}

# Known placeholder-only alternate v11 feeds — same xStock as the canonical
# mapping above, but a different Chainlink stream that publishes only the
# synthetic-low-bid pattern (bid ends in ``.01``, 100% of samples). These
# entries exist so that ``verify_v11_cadence.py`` can bucket samples per
# (canonical-vs-alternate, status) and emit per-feed-shape verdicts; the
# comparator (``score_weekend_comparison.py``) does NOT use this dict — it
# wants the canonical real-quote feed when one is available.
#
# Resolving these as "alternates of the same underlier" is empirical: their
# medians sit within ~0.06% of the canonical real-quote feeds at $208 and
# $376 respectively, and the alternates exhibit the canonical .01-suffix
# placeholder shape across 100% of samples in the 30000-sig deep scan
# (committed at 5e8e71d / referenced in the v11_cadence_verification report
# at 17063d6).
XSTOCK_V11_PLACEHOLDER_ALTERNATES: dict[str, str] = {
    "000b47988e89f3e63e1d679c84b774e6c38bb9929ad9de6e5e56d657a80388a9": "NVDAx",
    "000b67554457bf6c7e70d4d599d9634888fc8d79145c534ddd77ba1dae840107": "TSLAx",
}


def feed_id_to_xstock(feed_id: bytes | str) -> str | None:
    """Return the xStock symbol for any known feed_id (v10 canonical, v11
    canonical, or v11 placeholder-alternate), or ``None`` if unrecognised.

    Returns the bare symbol — ``feed_id_to_xstock_label()`` distinguishes
    canonical from placeholder-alternate by appending ``_alt`` to the symbol.
    Most consumers want this function (the score script labels samples by
    underlier, not by feed-shape); the verifier uses ``..._label()``.
    """
    if isinstance(feed_id, bytes):
        feed_id = feed_id.hex()
    fid = feed_id.lower().removeprefix("0x")
    if fid in XSTOCK_FEEDS:
        return XSTOCK_FEEDS[fid]
    if fid in XSTOCK_V11_FEEDS:
        return XSTOCK_V11_FEEDS[fid]
    if fid in XSTOCK_V11_PLACEHOLDER_ALTERNATES:
        return XSTOCK_V11_PLACEHOLDER_ALTERNATES[fid]
    return None


def feed_id_to_xstock_label(feed_id: bytes | str) -> str | None:
    """Like ``feed_id_to_xstock`` but distinguishes placeholder alternates by
    appending ``_alt`` to the symbol. Used by ``verify_v11_cadence.py`` to
    bucket canonical vs alternate feeds separately for §1.1 evidence —
    without this, the verifier would merge real-quote and placeholder
    samples for NVDAx/TSLAx into a single muddled per-symbol verdict.
    """
    if isinstance(feed_id, bytes):
        feed_id = feed_id.hex()
    fid = feed_id.lower().removeprefix("0x")
    if fid in XSTOCK_FEEDS:
        return XSTOCK_FEEDS[fid]
    if fid in XSTOCK_V11_FEEDS:
        return XSTOCK_V11_FEEDS[fid]
    if fid in XSTOCK_V11_PLACEHOLDER_ALTERNATES:
        return f"{XSTOCK_V11_PLACEHOLDER_ALTERNATES[fid]}_alt"
    return None


def xstock_feed_ids_bytes() -> dict[str, bytes]:
    """Return {symbol: feed_id_bytes} for the 8 v10 xStock feeds."""
    return {sym: bytes.fromhex(fid) for fid, sym in XSTOCK_FEEDS.items()}


def xstock_v11_feed_ids_bytes() -> dict[str, bytes]:
    """Return {symbol: feed_id_bytes} for the canonical v11 xStock feeds we
    have enumerated (currently 4 of 8 — see the module docstring for
    coverage). Excludes placeholder alternates."""
    return {sym: bytes.fromhex(fid) for fid, sym in XSTOCK_V11_FEEDS.items()}
