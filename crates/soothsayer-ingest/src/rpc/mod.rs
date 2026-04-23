//! Multi-provider Solana JSON-RPC client.
//!
//! Two providers are supported via an enum: [`Provider::RpcFast`] (default, 14
//! req/s on the Start tier) and [`Provider::Helius`] (free tier, 9 req/s, and
//! the only path for Helius-proprietary Enhanced Transactions v0). Each gets
//! its own [`limiter::RateLimiter`] so concurrent `rpc_batch` callers never
//! breach the per-provider per-second cap.
//!
//! **Why not JSON-RPC array batching.** Both free tiers reject array batch
//! payloads (Helius: 403 "Batch requests are only available for paid plans",
//! RPC Fast Start: 500 Internal Server Error on any array body). This module's
//! [`RpcClient::rpc_batch`] instead fans out N *individual* POSTs through a
//! bounded tokio join set, with every call consuming one rate-limit slot. That
//! matches the Python `rpc_batch` implementation and is the only path that
//! works on free tiers of both providers.
//!
//! Retries cover timeouts, connection resets, 429s, and 5xx responses with
//! exponential backoff (1s, 2s, 4s, 8s, 16s, 32s).

mod limiter;
mod retry;

pub use limiter::RateLimiter;

use std::sync::Arc;
use std::time::Duration;

use reqwest::StatusCode;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use thiserror::Error;
use tokio::sync::Semaphore;
use tokio::task::JoinSet;
use tracing::debug;

use crate::rpc::retry::{is_retriable_reqwest, with_retry};

/// RPC provider selection. `RpcFast` is the default because it serves more
/// requests per second (14 vs 9) and a larger monthly CU budget. `Helius`
/// stays available for Enhanced Transactions (DEX swap extraction) which
/// has no RPC Fast equivalent.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Provider {
    Helius,
    RpcFast,
}

impl Provider {
    /// Target RPS — one below each provider's documented cap.
    fn default_rps(self) -> f64 {
        match self {
            Provider::Helius => 9.0,
            Provider::RpcFast => 14.0,
        }
    }
}

/// Endpoint configuration per provider. Builder-style; fill in what you use.
#[derive(Clone, Debug, Default)]
pub struct RpcConfig {
    pub helius_url: Option<String>,
    pub rpcfast_url: Option<String>,
    pub primary: Option<Provider>,
}

impl RpcConfig {
    /// Read from env — mirrors the Python `config.py` contract.
    ///
    /// `HELIUS_API_KEY` → builds `https://mainnet.helius-rpc.com/?api-key=...`.
    /// `RPCFAST_API_KEY` + optional `RPCFAST_RPC_URL` → builds `<base>/?api_key=...`.
    /// `PRIMARY_RPC` ∈ {"helius", "rpcfast"} → overrides default primary.
    pub fn from_env() -> Self {
        let helius_url = std::env::var("HELIUS_API_KEY")
            .ok()
            .filter(|k| !k.is_empty())
            .map(|k| format!("https://mainnet.helius-rpc.com/?api-key={k}"));
        let rpcfast_url = std::env::var("RPCFAST_API_KEY")
            .ok()
            .filter(|k| !k.is_empty())
            .map(|k| {
                let base = std::env::var("RPCFAST_RPC_URL")
                    .unwrap_or_else(|_| "https://solana-rpc.rpcfast.com".to_string());
                format!("{base}/?api_key={k}")
            });
        let primary = std::env::var("PRIMARY_RPC").ok().and_then(|s| match s.to_lowercase().as_str() {
            "helius" => Some(Provider::Helius),
            "rpcfast" => Some(Provider::RpcFast),
            _ => None,
        });
        Self { helius_url, rpcfast_url, primary }
    }
}

#[derive(Debug, Error)]
pub enum RpcError {
    #[error("http error ({method}): {source}")]
    Http {
        method: String,
        #[source]
        source: reqwest::Error,
    },

    #[error("http status ({method}): {status}")]
    HttpStatus { method: String, status: StatusCode },

    #[error("rpc error from server ({method}): code={code} msg={message}")]
    Server { method: String, code: i64, message: String },

    #[error("response malformed ({method}): {reason}")]
    BadResponse { method: String, reason: String },

    #[error("provider {provider:?} not configured — set the corresponding env var")]
    ProviderNotConfigured { provider: Provider },

    #[error("unknown provider name {name:?}")]
    UnknownProvider { name: String },
}

pub type Result<T> = std::result::Result<T, RpcError>;

/// A `getSignaturesForAddress` record (strict subset of fields we consume).
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SignatureRecord {
    pub signature: String,
    pub slot: u64,
    #[serde(default)]
    pub block_time: Option<i64>,
    #[serde(default)]
    pub err: Option<Value>,
    #[serde(default)]
    pub memo: Option<String>,
}

/// Async JSON-RPC client. Clone is cheap (all fields are Arcs).
#[derive(Clone)]
pub struct RpcClient {
    http: reqwest::Client,
    providers: Arc<Providers>,
    primary: Provider,
}

struct Providers {
    helius: Option<ProviderState>,
    rpcfast: Option<ProviderState>,
}

struct ProviderState {
    url: String,
    limiter: RateLimiter,
}

impl RpcClient {
    pub fn new(config: RpcConfig) -> Self {
        let http = reqwest::Client::builder()
            .timeout(Duration::from_secs(30))
            .build()
            .expect("reqwest client builds with default tls config");
        let helius = config.helius_url.map(|url| ProviderState {
            url,
            limiter: RateLimiter::from_rps(Provider::Helius.default_rps()),
        });
        let rpcfast = config.rpcfast_url.map(|url| ProviderState {
            url,
            limiter: RateLimiter::from_rps(Provider::RpcFast.default_rps()),
        });
        // Default primary: RpcFast if available, else Helius, else explicit config.
        let primary = config.primary.unwrap_or_else(|| {
            if rpcfast.is_some() {
                Provider::RpcFast
            } else {
                Provider::Helius
            }
        });
        Self {
            http,
            providers: Arc::new(Providers { helius, rpcfast }),
            primary,
        }
    }

    pub fn primary(&self) -> Provider {
        self.primary
    }

    fn state(&self, provider: Provider) -> Result<&ProviderState> {
        let s = match provider {
            Provider::Helius => self.providers.helius.as_ref(),
            Provider::RpcFast => self.providers.rpcfast.as_ref(),
        };
        s.ok_or(RpcError::ProviderNotConfigured { provider })
    }

    /// Single JSON-RPC call.
    pub async fn rpc(
        &self,
        method: &str,
        params: Value,
        provider: Option<Provider>,
    ) -> Result<Value> {
        let provider = provider.unwrap_or(self.primary);
        let state = self.state(provider)?;
        let http = &self.http;
        let url = &state.url;
        let method_s = method.to_string();
        let body = json!({
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        });

        let method_for_err = method_s.clone();
        with_retry(
            || async {
                state.limiter.reserve().await;
                let resp = http.post(url).json(&body).send().await.map_err(|e| RpcError::Http {
                    method: method_for_err.clone(),
                    source: e,
                })?;
                let status = resp.status();
                if !status.is_success() {
                    return Err(RpcError::HttpStatus { method: method_for_err.clone(), status });
                }
                let raw: Value = resp.json().await.map_err(|e| RpcError::Http {
                    method: method_for_err.clone(),
                    source: e,
                })?;
                if let Some(err) = raw.get("error") {
                    let code = err.get("code").and_then(|v| v.as_i64()).unwrap_or(0);
                    let message = err
                        .get("message")
                        .and_then(|v| v.as_str())
                        .unwrap_or("")
                        .to_string();
                    return Err(RpcError::Server { method: method_for_err.clone(), code, message });
                }
                Ok(raw.get("result").cloned().unwrap_or(Value::Null))
            },
            is_retriable_rpc_error,
        )
        .await
    }

    /// Fan out N JSON-RPC calls concurrently. Rate limiting is per-provider and
    /// shared across this client's call sites, so batch calls never breach the
    /// per-second cap. Result order matches input order.
    ///
    /// `max_concurrent` bounds in-flight POSTs via a semaphore — saturates the
    /// rate limiter without overshooting the bound when one call is stuck in
    /// retry backoff. Defaults to `8` for Helius, `12` for RpcFast.
    pub async fn rpc_batch(
        &self,
        calls: Vec<(String, Value)>,
        provider: Option<Provider>,
    ) -> Result<Vec<Value>> {
        if calls.is_empty() {
            return Ok(Vec::new());
        }
        let provider = provider.unwrap_or(self.primary);
        let bound = match provider {
            Provider::Helius => 8,
            Provider::RpcFast => 12,
        };
        let sem = Arc::new(Semaphore::new(bound));
        let mut set = JoinSet::new();
        for (i, (method, params)) in calls.into_iter().enumerate() {
            let this = self.clone();
            let sem = Arc::clone(&sem);
            set.spawn(async move {
                let _permit = sem.acquire().await.expect("semaphore never closed");
                let out = this.rpc(&method, params, Some(provider)).await;
                (i, method, out)
            });
        }
        let mut results: Vec<Option<Value>> = (0..set.len()).map(|_| None).collect();
        let mut first_err: Option<(usize, String, RpcError)> = None;
        while let Some(joined) = set.join_next().await {
            let (i, method, r) = joined.expect("spawned task panicked");
            match r {
                Ok(v) => results[i] = Some(v),
                Err(e) if first_err.is_none() => first_err = Some((i, method, e)),
                Err(_) => {}
            }
        }
        if let Some((i, method, e)) = first_err {
            debug!(index = i, method = %method, error = %e, "rpc_batch failure");
            return Err(e);
        }
        Ok(results.into_iter().map(|o| o.unwrap_or(Value::Null)).collect())
    }

    /// One page of confirmed signatures for an address, newest-first.
    pub async fn get_signatures_for_address(
        &self,
        address: &str,
        before: Option<&str>,
        until: Option<&str>,
        limit: u32,
        provider: Option<Provider>,
    ) -> Result<Vec<SignatureRecord>> {
        let mut opts = serde_json::Map::new();
        opts.insert("limit".into(), json!(limit));
        if let Some(b) = before {
            opts.insert("before".into(), json!(b));
        }
        if let Some(u) = until {
            opts.insert("until".into(), json!(u));
        }
        let result = self
            .rpc(
                "getSignaturesForAddress",
                json!([address, Value::Object(opts)]),
                provider,
            )
            .await?;
        if result.is_null() {
            return Ok(Vec::new());
        }
        let sigs: Vec<SignatureRecord> =
            serde_json::from_value(result).map_err(|e| RpcError::BadResponse {
                method: "getSignaturesForAddress".to_string(),
                reason: format!("deserialise sig list: {e}"),
            })?;
        Ok(sigs)
    }

    /// Fetch a full transaction by signature. Returns `None` if not found /
    /// pruned from the node's retention window.
    pub async fn get_transaction(
        &self,
        signature: &str,
        provider: Option<Provider>,
    ) -> Result<Option<Value>> {
        let params = json!([
            signature,
            { "encoding": "jsonParsed", "maxSupportedTransactionVersion": 0 }
        ]);
        let result = self.rpc("getTransaction", params, provider).await?;
        if result.is_null() {
            Ok(None)
        } else {
            Ok(Some(result))
        }
    }
}

fn is_retriable_rpc_error(err: &RpcError) -> bool {
    match err {
        RpcError::Http { source, .. } => is_retriable_reqwest(source),
        RpcError::HttpStatus { status, .. } => is_retriable_status(*status),
        _ => false,
    }
}

// Re-export for downstream consumers and for tests.
pub use retry::is_retriable_status;
