//! Source-specific ingest modules. Each submodule is the Rust counterpart to
//! its Python equivalent in `src/soothsayer/sources/` — same wire protocols,
//! same decoders, just async-first and strongly-typed.
//!
//! The only source implemented today is [`chainlink`]. Kraken perps, Helius
//! RPC, and Yahoo minute-bars will follow as the async runtime lands.

pub mod chainlink;

pub use chainlink::v10::V10Report;
