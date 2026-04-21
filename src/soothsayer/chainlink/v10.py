"""
Chainlink Data Streams v10 report decoder.

v10 is the schema currently in use on Solana mainnet for the 24/5 US-equity
streams that back xStocks (as of April 2026). Despite Chainlink's public docs
referring to "v11" as the equity schema, the actual on-chain Verifier traffic
for xStock feeds uses schema ID 0x000a (v10). v10 is structurally v11 minus
the `market_status` field.

Field order determined by empirically inspecting live Verifier instruction data
and cross-checking decoded prices against yfinance live quotes for 8 xStocks
(SPY, QQQ, GOOGL, AAPL, NVDA, TSLA, MSTR, HOOD). Layout:

  w0   feed_id                bytes32   (first 2 bytes = 0x000a)
  w1   valid_from_timestamp   u32
  w2   observations_timestamp u32
  w3   native_fee             u192
  w4   link_fee               u192
  w5   expires_at             u32
  w6   last_seen_timestamp_ns u64       (stored as nanoseconds)
  w7   mid                    i192      (DON-consensus benchmark, 1e18-scaled)
  w8   bid                    i192
  w9   bid_volume             i192
  w10  ask                    i192
  w11  ask_volume             i192
  w12  last_traded_price      i192

Total: 13 words × 32 = 416 bytes.

`market_status` (available in v11) is NOT present in v10. To determine whether
an observation is "weekend / closed" we compare `observations_timestamp` to the
NYSE trading calendar instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Final

WORD: Final[int] = 32
REPORT_LEN: Final[int] = 13 * WORD  # 416 bytes
PRICE_SCALE: Final[int] = 10**18


@dataclass(frozen=True)
class V10Report:
    feed_id: bytes
    valid_from_timestamp: int
    observations_timestamp: int
    native_fee: int
    link_fee: int
    expires_at: int
    last_seen_timestamp_ns: int
    mid_raw: int
    bid_raw: int
    bid_volume_raw: int
    ask_raw: int
    ask_volume_raw: int
    last_traded_price_raw: int

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


def _word(data: bytes, idx: int) -> bytes:
    return data[idx * WORD : (idx + 1) * WORD]


def _uint(data: bytes, idx: int) -> int:
    return int.from_bytes(_word(data, idx), "big", signed=False)


def _int(data: bytes, idx: int) -> int:
    # i192 is sign-extended across the full 32-byte slot; signed 256-bit decode works.
    return int.from_bytes(_word(data, idx), "big", signed=True)


def decode(report: bytes) -> V10Report:
    if len(report) < REPORT_LEN:
        raise ValueError(f"report too short: {len(report)} bytes, need >= {REPORT_LEN}")
    return V10Report(
        feed_id=_word(report, 0),
        valid_from_timestamp=_uint(report, 1),
        observations_timestamp=_uint(report, 2),
        native_fee=_uint(report, 3),
        link_fee=_uint(report, 4),
        expires_at=_uint(report, 5),
        last_seen_timestamp_ns=_uint(report, 6),
        mid_raw=_int(report, 7),
        bid_raw=_int(report, 8),
        bid_volume_raw=_int(report, 9),
        ask_raw=_int(report, 10),
        ask_volume_raw=_int(report, 11),
        last_traded_price_raw=_int(report, 12),
    )
