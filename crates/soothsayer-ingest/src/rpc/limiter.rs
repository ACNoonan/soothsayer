//! Async token-bucket-ish rate limiter.
//!
//! Callers reserve a slot `min_interval` after the previous reservation. The
//! next-slot clock is guarded by a tokio [`Mutex`], and sleeping happens after
//! releasing the lock so concurrent callers queue up their slots immediately
//! instead of serialising on the sleep itself. This matches the thread-pool
//! pattern used by the Python `helius.py` and gives the same throughput
//! guarantee when an `RpcClient` fans out N `rpc_batch` calls on a shared pool.

use std::time::Duration;

use tokio::sync::Mutex;
use tokio::time::{sleep, Instant};

#[derive(Debug)]
pub struct RateLimiter {
    min_interval: Duration,
    next_slot: Mutex<Instant>,
}

impl RateLimiter {
    pub fn new(min_interval: Duration) -> Self {
        Self { min_interval, next_slot: Mutex::new(Instant::now()) }
    }

    pub fn from_rps(rps: f64) -> Self {
        debug_assert!(rps > 0.0, "rps must be positive");
        Self::new(Duration::from_secs_f64(1.0 / rps))
    }

    pub async fn reserve(&self) {
        let wait = {
            let mut slot = self.next_slot.lock().await;
            let now = Instant::now();
            let claimed = (*slot).max(now);
            *slot = claimed + self.min_interval;
            claimed.saturating_duration_since(now)
        };
        if !wait.is_zero() {
            sleep(wait).await;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Arc;

    #[tokio::test]
    async fn reservations_are_spaced_by_min_interval() {
        let lim = Arc::new(RateLimiter::new(Duration::from_millis(50)));
        let start = Instant::now();
        for _ in 0..4 {
            lim.reserve().await;
        }
        let elapsed = start.elapsed();
        // 4 reservations at 50ms spacing → the first is immediate, the rest each
        // wait 50ms. Total ≥ 150ms, allow up to 300ms slack for timer jitter.
        assert!(
            elapsed >= Duration::from_millis(150),
            "elapsed {elapsed:?} < 150ms"
        );
        assert!(
            elapsed < Duration::from_millis(400),
            "elapsed {elapsed:?} >= 400ms (too much overhead)"
        );
    }

    #[tokio::test(flavor = "multi_thread", worker_threads = 4)]
    async fn concurrent_reservations_serialise_cleanly() {
        let lim = Arc::new(RateLimiter::new(Duration::from_millis(30)));
        let start = Instant::now();
        let mut handles = Vec::new();
        for _ in 0..6 {
            let lim = Arc::clone(&lim);
            handles.push(tokio::spawn(async move {
                lim.reserve().await;
                Instant::now()
            }));
        }
        let mut stamps = Vec::new();
        for h in handles {
            stamps.push(h.await.unwrap());
        }
        stamps.sort();
        // 6 reservations at 30ms spacing → total >= 150ms (5 waits of 30ms).
        let elapsed = stamps.last().unwrap().duration_since(start);
        assert!(elapsed >= Duration::from_millis(140), "elapsed {elapsed:?}");
        // No two should land within < min_interval of each other.
        for pair in stamps.windows(2) {
            let gap = pair[1].duration_since(pair[0]);
            assert!(
                gap >= Duration::from_millis(25),
                "gap {gap:?} too small between consecutive reservations"
            );
        }
    }
}
