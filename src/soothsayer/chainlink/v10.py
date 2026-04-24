"""
Chainlink Data Streams v10 (Tokenized Asset) report decoder.

Schema used on Solana mainnet for xStock feeds (schema ID 0x000a). Corresponds
to the "Tokenized Asset" schema in Chainlink's public docs — *not* the v11
"RWA Advanced" schema. v10 is specialised for tokenised equities: it carries
an underlying-venue `price` plus a 24/7 CEX-aggregated `tokenizedPrice` plus
corporate-action multipliers. It does NOT carry bid/ask or order book depth.

ABI layout (13 words × 32 = 416 bytes total; each field padded to a 32-byte
slot regardless of its Solidity width):

  w0   feedId                    bytes32    (first 2 bytes = 0x000a)
  w1   validFromTimestamp        uint32     (seconds)
  w2   observationsTimestamp     uint32     (seconds)
  w3   nativeFee                 uint192
  w4   linkFee                   uint192
  w5   expiresAt                 uint32     (seconds)
  w6   lastUpdateTimestamp       uint64     (nanoseconds)
  w7   price                     int192     (last traded on underlying; STALE on
                                             weekends/holidays when the venue is closed;
                                             1e18-scaled)
  w8   marketStatus              uint32     (0 = Unknown, 1 = Closed, 2 = Open)
  w9   currentMultiplier         int192     (corporate-action multiplier applied to
                                             tokenizedPrice right now; typically 1e18)
  w10  newMultiplier             int192     (future multiplier, 0 if none scheduled)
  w11  activationDateTime        uint32     (seconds; 0 if no corp action scheduled)
  w12  tokenizedPrice            int192     (24/7 CEX-aggregated mark, updates weekends;
                                             1e18-scaled — this is what V5 compares to DEX)

Field semantics confirmed against live on-chain data for SPYx (2026-04-24):
during US trading hours with SPY at ~711, w7=708.585 and w12=711.460, with
marketStatus=1. Only `tokenizedPrice` (w12) tracks the real 24/7 mark; `price`
(w7) is for consumers who want the traditional venue last-trade.

Historical note: an earlier decoder in this repo mislabeled w7 as "mid" and
w8-w11 as bid/ask/volumes. That layout doesn't exist in v10. It caused V1's
weekend-bias analysis to silently compare Friday close to Monday open (because
w7 is a frozen venue-last-trade outside market hours), producing a meaningless
residual. Any V1 run prior to this fix needs to be re-executed against
`tokenized_price` to be valid.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Final

WORD: Final[int] = 32
REPORT_LEN: Final[int] = 13 * WORD  # 416 bytes
PRICE_SCALE: Final[int] = 10**18
NS_PER_S: Final[int] = 10**9

MARKET_STATUS_UNKNOWN: Final[int] = 0
MARKET_STATUS_CLOSED: Final[int] = 1
MARKET_STATUS_OPEN: Final[int] = 2


@dataclass(frozen=True)
class V10Report:
    feed_id: bytes
    valid_from_timestamp: int
    observations_timestamp: int
    native_fee: int
    link_fee: int
    expires_at: int
    last_update_timestamp_ns: int
    price_raw: int
    market_status: int
    current_multiplier_raw: int
    new_multiplier_raw: int
    activation_datetime: int
    tokenized_price_raw: int

    @property
    def feed_id_hex(self) -> str:
        return "0x" + self.feed_id.hex()

    @property
    def price(self) -> Decimal:
        """Last-traded on underlying venue. Stale when market is Closed."""
        return Decimal(self.price_raw) / Decimal(PRICE_SCALE)

    @property
    def tokenized_price(self) -> Decimal:
        """24/7 CEX-aggregated mark. This is what V5 treats as 'the Chainlink mark'."""
        return Decimal(self.tokenized_price_raw) / Decimal(PRICE_SCALE)

    @property
    def current_multiplier(self) -> Decimal:
        return Decimal(self.current_multiplier_raw) / Decimal(PRICE_SCALE)

    @property
    def new_multiplier(self) -> Decimal:
        return Decimal(self.new_multiplier_raw) / Decimal(PRICE_SCALE)

    @property
    def observations_at(self) -> datetime:
        return datetime.fromtimestamp(self.observations_timestamp, tz=UTC)

    @property
    def last_update_at(self) -> datetime:
        return datetime.fromtimestamp(self.last_update_timestamp_ns / NS_PER_S, tz=UTC)

    @property
    def is_market_open(self) -> bool:
        return self.market_status == MARKET_STATUS_OPEN


def _word(data: bytes, idx: int) -> bytes:
    return data[idx * WORD : (idx + 1) * WORD]


def _uint(data: bytes, idx: int) -> int:
    return int.from_bytes(_word(data, idx), "big", signed=False)


def _int(data: bytes, idx: int) -> int:
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
        last_update_timestamp_ns=_uint(report, 6),
        price_raw=_int(report, 7),
        market_status=_uint(report, 8),
        current_multiplier_raw=_int(report, 9),
        new_multiplier_raw=_int(report, 10),
        activation_datetime=_uint(report, 11),
        tokenized_price_raw=_int(report, 12),
    )
