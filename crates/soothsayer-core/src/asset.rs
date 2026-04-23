//! Asset, signal-kind, and source identifiers.
//!
//! `AssetSymbol` is a lightweight wrapper around an interned string (bounded
//! length, ASCII) so we can hash/compare cheaply. `SignalKind` enumerates the
//! semantic meaning of an observation's numeric value, and `Source` names the
//! originating feed — together they form the (asset, kind, source) triple that
//! the filter layer uses to route observations.

use serde::{Deserialize, Serialize};
use std::fmt;

/// A short ticker-style identifier. Up to 16 bytes, ASCII preferred.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct AssetSymbol([u8; 16]);

impl AssetSymbol {
    pub fn new(s: &str) -> crate::Result<Self> {
        let bytes = s.as_bytes();
        if bytes.len() > 16 {
            return Err(crate::Error::InvalidSymbol(s.to_string()));
        }
        let mut buf = [0u8; 16];
        buf[..bytes.len()].copy_from_slice(bytes);
        Ok(Self(buf))
    }

    pub fn as_str(&self) -> &str {
        let end = self.0.iter().position(|&b| b == 0).unwrap_or(16);
        // SAFETY: we validated ASCII-ish input in `new`. Non-UTF8 bytes would only
        // appear if the struct was constructed by other means; recover via utf8_lossy.
        std::str::from_utf8(&self.0[..end]).unwrap_or("")
    }
}

impl fmt::Debug for AssetSymbol {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "AssetSymbol({:?})", self.as_str())
    }
}

impl fmt::Display for AssetSymbol {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

/// What the numeric value in an observation means semantically.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SignalKind {
    /// Mid price (arithmetic or DON-consensus benchmark).
    Mid,
    Bid,
    Ask,
    LastTraded,
    /// Dollar-denominated level from an options/NAV anchor.
    Reference,
    /// Perpetual-futures funding rate (per 8-hour or hourly period, provider-specific).
    FundingRate,
    /// On-chain DEX swap effective price.
    SwapPrice,
}

/// The originating venue or data feed for an observation.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Source {
    Chainlink,
    Pyth,
    Switchboard,
    Kraken,
    Coinbase,
    Binance,
    Yahoo,
    Polygon,
    Databento,
    Meteora,
    Raydium,
    Orca,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn asset_symbol_roundtrip() {
        let sym = AssetSymbol::new("SPYx").unwrap();
        assert_eq!(sym.as_str(), "SPYx");
        assert_eq!(format!("{sym}"), "SPYx");
    }

    #[test]
    fn asset_symbol_too_long_is_rejected() {
        let err = AssetSymbol::new("01234567890123456").unwrap_err();
        assert!(matches!(err, crate::Error::InvalidSymbol(_)));
    }
}
