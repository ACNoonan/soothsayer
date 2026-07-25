//! The `receipt` command: fetch a live `PriceUpdate` account over
//! JSON-RPC and decode it with the `soothsayer-consumer` crate — the
//! same decoder integrators link, so a passing decode here dogfoods the
//! consumer contract.
//!
//! Exit codes: 0 = decoded and invariants hold; 1 = decode/invariant
//! failure; 2 = network/account error.

use std::error::Error;

use base64::Engine;
use soothsayer_consumer::{decode_price_update, PriceBand, Regime};

fn rpc_url(alias: &str) -> String {
    match alias {
        "devnet" => "https://api.devnet.solana.com".to_string(),
        "mainnet" => "https://api.mainnet-beta.solana.com".to_string(),
        other => other.to_string(),
    }
}

pub fn run(account: &str, url: &str, json: bool) -> i32 {
    match fetch_account(account, &rpc_url(url)) {
        Ok(data) => match decode_price_update(&data) {
            Ok(band) => {
                let invariants = band.validate_invariants();
                print_band(account, &band, invariants.err().map(|e| e.to_string()), json);
                i32::from(!matches!(band.validate_invariants(), Ok(())))
            }
            Err(e) => {
                eprintln!("decode failed: {e}");
                1
            }
        },
        Err(e) => {
            eprintln!("error: {e}");
            2
        }
    }
}

fn fetch_account(account: &str, url: &str) -> Result<Vec<u8>, Box<dyn Error>> {
    let body = serde_json::json!({
        "jsonrpc": "2.0", "id": 1, "method": "getAccountInfo",
        "params": [account, {"encoding": "base64"}],
    });
    let resp: serde_json::Value = crate::http::client()?.post(url).json(&body).send()?.json()?;
    if let Some(err) = resp.get("error") {
        return Err(format!("RPC error: {err}").into());
    }
    let value = resp.pointer("/result/value");
    if value.is_none() || value == Some(&serde_json::Value::Null) {
        return Err(format!("account {account} not found on {url}").into());
    }
    let b64 = resp
        .pointer("/result/value/data/0")
        .and_then(|d| d.as_str())
        .ok_or("unexpected RPC response shape (no base64 data)")?;
    Ok(base64::engine::general_purpose::STANDARD.decode(b64)?)
}

fn print_band(account: &str, band: &PriceBand, invariant_err: Option<String>, json: bool) {
    let regime = Regime::from_code(band.regime_code)
        .map(|r| r.as_str().to_string())
        .unwrap_or_else(|| format!("unknown({})", band.regime_code));
    let forecaster = band
        .forecaster()
        .map(|f| f.as_str().to_string())
        .unwrap_or_else(|| format!("unknown({})", band.forecaster_code));
    let profile = band
        .profile()
        .map(|p| p.as_str().to_string())
        .unwrap_or_else(|| format!("unknown({})", band.profile_code));
    if json {
        let out = serde_json::json!({
            "account": account,
            "symbol": band.symbol_str(),
            "version": band.version,
            "point": band.point_f64(),
            "lower": band.lower_f64(),
            "upper": band.upper_f64(),
            "half_width_bps": band.half_width_bps(),
            "fri_close": band.fri_close_f64(),
            "target_coverage_bps": band.target_coverage_bps,
            "claimed_served_bps": band.claimed_served_bps,
            "buffer_applied_bps": band.buffer_applied_bps,
            "regime": regime,
            "forecaster": forecaster,
            "profile": profile,
            "fri_ts": band.fri_ts,
            "publish_ts": band.publish_ts,
            "publish_slot": band.publish_slot,
            "signer_hex": hex::encode(band.signer),
            "signer_epoch": band.signer_epoch,
            "invariants": invariant_err.clone().map_or(serde_json::json!("ok"),
                                                       |e| serde_json::json!({"violated": e})),
        });
        println!("{}", serde_json::to_string_pretty(&out).unwrap());
    } else {
        println!("PriceUpdate {account}");
        println!("  symbol            {}", band.symbol_str());
        println!(
            "  band              [{:.6}, {:.6}]  point {:.6}  ({:.1} bps half-width)",
            band.lower_f64(),
            band.upper_f64(),
            band.point_f64(),
            band.half_width_bps()
        );
        println!(
            "  coverage          target {} bps  claimed {} bps  buffer {} bps",
            band.target_coverage_bps, band.claimed_served_bps, band.buffer_applied_bps
        );
        println!("  regime            {regime}");
        println!("  forecaster        {forecaster}   profile {profile}");
        println!(
            "  fri_close         {:.6}   fri_ts {}   publish_ts {}   slot {}",
            band.fri_close_f64(),
            band.fri_ts,
            band.publish_ts,
            band.publish_slot
        );
        println!("  signer            {}", hex::encode(band.signer));
        println!("  signer_epoch      {}", band.signer_epoch);
        match invariant_err {
            None => println!("  invariants        ok (lower ≤ point ≤ upper, version, bps ranges)"),
            Some(e) => println!("  invariants        VIOLATED: {e}"),
        }
    }
}
