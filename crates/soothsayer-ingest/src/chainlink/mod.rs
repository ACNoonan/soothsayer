//! Chainlink Data Streams decoders.
//!
//! As of April 2026 the xStock equity feeds on Solana mainnet use schema v10
//! (first two bytes of the feed ID = `0x000a`), not v11 (`0x000b`) as
//! Chainlink's public docs describe. v10 is v11 minus the `market_status`
//! field. This module currently implements v10; v11 will be added once
//! Chainlink rolls it out on-chain for xStock streams.

pub mod v10;
