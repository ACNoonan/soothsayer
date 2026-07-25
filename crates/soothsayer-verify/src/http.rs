//! Shared blocking HTTP client. Rustls-only so the released binary is
//! self-contained (no system TLS dependency).

use std::error::Error;

/// Browser-shaped User-Agent: Yahoo's chart gate rejects tool-shaped
/// UAs (verified against the scryer daily fetcher, 2026-06). Keep in
/// sync with `scryer-fetch-equities::yahoo_daily::DEFAULT_USER_AGENT`.
pub const USER_AGENT: &str =
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 \
     (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36";

pub fn client() -> Result<reqwest::blocking::Client, Box<dyn Error>> {
    Ok(reqwest::blocking::Client::builder()
        .user_agent(USER_AGENT)
        .timeout(std::time::Duration::from_secs(30))
        .build()?)
}

pub fn get_text(url: &str) -> Result<String, Box<dyn Error>> {
    let resp = client()?.get(url).send()?;
    if !resp.status().is_success() {
        return Err(format!("GET {url} -> HTTP {}", resp.status()).into());
    }
    Ok(resp.text()?)
}
