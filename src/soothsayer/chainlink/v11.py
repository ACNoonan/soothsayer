"""
Chainlink Data Streams v11 report decoder.

v11 is used for 24/5 US equity streams (xStocks, since Jan 2026). The payload is
ABI-encoded: 14 fields, one 32-byte word each, total 448 bytes. Integer fields
are big-endian and right-aligned in their word; i192 fields are sign-extended
across the full 32-byte word so we can safely decode each word as a signed
256-bit integer.

Schema reference:
  smartcontractkit/data-streams-sdk/rust/crates/report/src/report/v11.rs

Field order (word 0 .. word 13):
  0: feed_id                bytes32
  1: valid_from_timestamp   u32
  2: observations_timestamp u32
  3: native_fee             u192
  4: link_fee               u192
  5: expires_at             u32
  6: mid                    i192   <-- the DON-consensus benchmark price
  7: last_seen_timestamp_ns u64
  8: bid                    i192
  9: bid_volume             i192
 10: ask                    i192
 11: ask_volume             i192
 12: last_traded_price      i192
 13: market_status          u32

`market_status` values (24/5 US equities, per Chainlink docs):
  0 Unknown, 1 Pre-market, 2 Regular, 3 Post-market, 4 Overnight, 5 Closed
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Final

WORD: Final[int] = 32
REPORT_LEN: Final[int] = 14 * WORD  # 448 bytes
PRICE_SCALE: Final[int] = 10**18    # 18-decimal fixed point

MARKET_STATUS = {
    0: "unknown",
    1: "pre_market",
    2: "regular",
    3: "post_market",
    4: "overnight",
    5: "closed",  # covers weekends
}


@dataclass(frozen=True)
class V11Report:
    feed_id: bytes                 # 32 bytes
    valid_from_timestamp: int      # unix seconds
    observations_timestamp: int    # unix seconds
    native_fee: int                # raw (wei-scale)
    link_fee: int                  # raw (wei-scale)
    expires_at: int                # unix seconds
    mid_raw: int                   # 18-decimal fixed point
    last_seen_timestamp_ns: int    # unix nanoseconds
    bid_raw: int
    bid_volume_raw: int
    ask_raw: int
    ask_volume_raw: int
    last_traded_price_raw: int
    market_status: int             # 0..5

    @property
    def feed_id_hex(self) -> str:
        return "0x" + self.feed_id.hex()

    @property
    def mid(self) -> Decimal:
        return Decimal(self.mid_raw) / Decimal(PRICE_SCALE)

    @property
    def bid(self) -> Decimal:
        return Decimal(self.bid_raw) / Decimal(PRICE_SCALE)

    @property
    def ask(self) -> Decimal:
        return Decimal(self.ask_raw) / Decimal(PRICE_SCALE)

    @property
    def last_traded_price(self) -> Decimal:
        return Decimal(self.last_traded_price_raw) / Decimal(PRICE_SCALE)

    @property
    def observations_at(self) -> datetime:
        return datetime.fromtimestamp(self.observations_timestamp, tz=UTC)

    @property
    def market_status_label(self) -> str:
        return MARKET_STATUS.get(self.market_status, f"unknown({self.market_status})")


def _word(data: bytes, idx: int) -> bytes:
    return data[idx * WORD : (idx + 1) * WORD]


def _read_uint(data: bytes, idx: int) -> int:
    return int.from_bytes(_word(data, idx), "big", signed=False)


def _read_int(data: bytes, idx: int) -> int:
    # i192 is sign-extended across the full 32-byte word, so signed 256-bit
    # interpretation is correct.
    return int.from_bytes(_word(data, idx), "big", signed=True)


def decode(report: bytes) -> V11Report:
    """Decode a 448-byte v11 raw report payload. Raises if length is wrong."""
    if len(report) < REPORT_LEN:
        raise ValueError(f"report too short: {len(report)} bytes, need >= {REPORT_LEN}")
    return V11Report(
        feed_id=_word(report, 0),
        valid_from_timestamp=_read_uint(report, 1),
        observations_timestamp=_read_uint(report, 2),
        native_fee=_read_uint(report, 3),
        link_fee=_read_uint(report, 4),
        expires_at=_read_uint(report, 5),
        mid_raw=_read_int(report, 6),
        last_seen_timestamp_ns=_read_uint(report, 7),
        bid_raw=_read_int(report, 8),
        bid_volume_raw=_read_int(report, 9),
        ask_raw=_read_int(report, 10),
        ask_volume_raw=_read_int(report, 11),
        last_traded_price_raw=_read_int(report, 12),
        market_status=_read_uint(report, 13),
    )


def plausible_v11_prefix(candidate: bytes) -> bool:
    """Heuristic: does `candidate[:448]` parse as a sane 2026-era equity report?

    Sanity checks:
      - observations_timestamp in [2025-01-01, 2028-01-01]
      - mid_raw corresponds to USD price in [0.01, 100_000]
      - market_status in 0..5
    Used for the one-shot task of locating the report offset inside instruction data.
    """
    if len(candidate) < REPORT_LEN:
        return False
    try:
        r = decode(candidate[:REPORT_LEN])
    except Exception:
        return False
    if not (1_735_689_600 <= r.observations_timestamp <= 1_830_297_600):
        return False
    mid = r.mid
    if not (Decimal("0.01") <= mid <= Decimal(100_000)):
        return False
    if r.market_status not in MARKET_STATUS:
        return False
    return True
