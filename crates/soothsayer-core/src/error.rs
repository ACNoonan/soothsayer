//! Shared error type.

use thiserror::Error;

pub type Result<T> = std::result::Result<T, Error>;

#[derive(Debug, Error)]
pub enum Error {
    #[error("invalid asset symbol: {0:?}")]
    InvalidSymbol(String),

    #[error("decode failed: {0}")]
    Decode(String),

    #[error("value out of range for representation: {0}")]
    OutOfRange(String),
}
