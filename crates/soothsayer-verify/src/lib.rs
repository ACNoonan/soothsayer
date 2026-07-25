//! `soothsayer-verify` — run your own Soothsayer verifier.
//!
//! Independently audits Soothsayer's published band coverage claims:
//! reads the public band archive (claims only), fetches realised
//! Monday opens itself from Yahoo, and recomputes the coverage
//! statistics with its own implementations (parity-pinned against
//! scipy, never shared with the pipeline that produced the claims).
//! See the crate README for the trust model and tier definitions.

pub mod archive;
pub mod artefact;
pub mod coverage;
pub mod http;
pub mod receipt;
pub mod stats;
pub mod truth;
