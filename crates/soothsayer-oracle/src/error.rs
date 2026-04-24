//! Oracle error types.

use thiserror::Error;

pub type OracleResult<T> = std::result::Result<T, OracleError>;

#[derive(Debug, Error)]
pub enum OracleError {
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

    #[error("data integrity: {0}")]
    Integrity(String),
}
