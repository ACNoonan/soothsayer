//! Shared domain types for the soothsayer fair-value oracle.
//!
//! This crate is intentionally small. It defines the vocabulary used across the
//! ingest, filter, and publisher layers: an [`Observation`] record, the
//! [`AssetSymbol`] and [`Source`] identifiers, and a shared [`Error`] type.
//!
//! Downstream crates build on these types rather than re-inventing their own.

pub mod asset;
pub mod error;
pub mod observation;

pub use asset::{AssetSymbol, SignalKind, Source};
pub use error::{Error, Result};
pub use observation::Observation;
