//! Retry-with-exponential-backoff for transient RPC errors.
//!
//! Mirrors the Python `_with_retry` contract: retry on connection errors,
//! timeouts, 429s, and 5xx responses. Base delay 1s, doubling each attempt
//! (1, 2, 4, 8, 16, 32 seconds at attempts=6), 6 attempts total.

use std::future::Future;
use std::time::Duration;

use reqwest::StatusCode;
use tokio::time::sleep;

pub const DEFAULT_ATTEMPTS: u32 = 6;
pub const DEFAULT_BASE_DELAY: Duration = Duration::from_secs(1);

/// Is this `reqwest::Error` worth retrying?
pub fn is_retriable_reqwest(e: &reqwest::Error) -> bool {
    if e.is_timeout() || e.is_connect() {
        return true;
    }
    if let Some(status) = e.status() {
        return is_retriable_status(status);
    }
    false
}

/// 429 and 5xx are transient; 4xx otherwise is not.
pub fn is_retriable_status(s: StatusCode) -> bool {
    s == StatusCode::TOO_MANY_REQUESTS || s.is_server_error()
}

/// Run `f` up to `attempts` times, sleeping `base_delay * 2^i` between tries.
/// `retriable` decides whether a given error should trigger another attempt.
pub async fn with_retry_cfg<F, Fut, T, E>(
    attempts: u32,
    base_delay: Duration,
    mut f: F,
    retriable: impl Fn(&E) -> bool,
) -> std::result::Result<T, E>
where
    F: FnMut() -> Fut,
    Fut: Future<Output = std::result::Result<T, E>>,
{
    let mut last_err: Option<E> = None;
    for i in 0..attempts {
        match f().await {
            Ok(v) => return Ok(v),
            Err(e) => {
                let is_last = i == attempts - 1;
                if !retriable(&e) || is_last {
                    return Err(e);
                }
                last_err = Some(e);
                sleep(base_delay * (1 << i)).await;
            }
        }
    }
    Err(last_err.expect("loop body always sets last_err on non-return path"))
}

/// Default settings: 6 attempts, 1s base.
pub async fn with_retry<F, Fut, T, E>(
    f: F,
    retriable: impl Fn(&E) -> bool,
) -> std::result::Result<T, E>
where
    F: FnMut() -> Fut,
    Fut: Future<Output = std::result::Result<T, E>>,
{
    with_retry_cfg(DEFAULT_ATTEMPTS, DEFAULT_BASE_DELAY, f, retriable).await
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU32, Ordering};
    use std::sync::Arc;

    #[tokio::test]
    async fn retries_flake_then_succeeds() {
        let counter = Arc::new(AtomicU32::new(0));
        let counter_inner = Arc::clone(&counter);
        let result: Result<&'static str, &'static str> = with_retry_cfg(
            4,
            Duration::from_millis(1),
            || {
                let counter = Arc::clone(&counter_inner);
                async move {
                    let n = counter.fetch_add(1, Ordering::SeqCst);
                    if n < 2 {
                        Err("flake")
                    } else {
                        Ok("ok")
                    }
                }
            },
            |_| true,
        )
        .await;
        assert_eq!(result.unwrap(), "ok");
        assert_eq!(counter.load(Ordering::SeqCst), 3);
    }

    #[tokio::test]
    async fn bails_out_on_non_retriable_error() {
        let counter = Arc::new(AtomicU32::new(0));
        let counter_inner = Arc::clone(&counter);
        let result: Result<(), &'static str> = with_retry_cfg(
            5,
            Duration::from_millis(1),
            || {
                let counter = Arc::clone(&counter_inner);
                async move {
                    counter.fetch_add(1, Ordering::SeqCst);
                    Err("non-retriable")
                }
            },
            |e| *e == "flake",
        )
        .await;
        assert!(result.is_err());
        assert_eq!(counter.load(Ordering::SeqCst), 1);
    }

    #[test]
    fn status_classifier() {
        assert!(is_retriable_status(StatusCode::TOO_MANY_REQUESTS));
        assert!(is_retriable_status(StatusCode::INTERNAL_SERVER_ERROR));
        assert!(is_retriable_status(StatusCode::BAD_GATEWAY));
        assert!(!is_retriable_status(StatusCode::FORBIDDEN));
        assert!(!is_retriable_status(StatusCode::NOT_FOUND));
    }
}
