//! Oracle error types.

use thiserror::Error;

pub type Result<T, E = Error> = std::result::Result<T, E>;

#[derive(Debug, Error)]
pub enum Error {
    #[error("io: {0}")]
    Io(#[from] std::io::Error),

    #[error("polars: {0}")]
    Polars(#[from] polars::error::PolarsError),

    #[error("missing required column {column:?} in {artifact:?}")]
    MissingColumn { column: String, artifact: String },

    #[error("no bounds available for symbol={symbol:?} as_of={as_of}")]
    NoBounds { symbol: String, as_of: chrono::NaiveDate },

    #[error("unknown regime {0:?}; must be one of normal | long_weekend | high_vol")]
    UnknownRegime(String),

    #[error("unknown symbol_class for {0:?}; not in the M6b2 lending mapping")]
    UnknownSymbolClass(String),

    #[error("data integrity: {0}")]
    Integrity(String),
}
