//! Source-specific ingest modules. Each submodule is the Rust counterpart to
//! its Python equivalent in `src/soothsayer/sources/` — same wire protocols,
//! same decoders, just async-first and strongly-typed.
//!
//! Two layers live here:
//!
//! - [`rpc`] — multi-provider Solana JSON-RPC client (RPC Fast + Helius) with
//!   per-provider rate limiting and retry-with-backoff. The foundation used by
//!   every on-chain source.
//! - [`chainlink`] — Chainlink Data Streams decoders (v10 today).

pub mod chainlink;
pub mod rpc;

pub use chainlink::v10::V10Report;
pub use rpc::{Provider, RpcClient, RpcConfig, RpcError, SignatureRecord};
