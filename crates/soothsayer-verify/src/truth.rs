//! Independent truth acquisition: regular-session daily opens from the
//! Yahoo v8 chart API, fetched by the verifier itself — never from
//! Soothsayer infrastructure (that separation is what makes the audit
//! non-circular). Same source/convention as the evaluation panel.
//!
//! Split renormalisation: archive bands are recorded on the as-traded
//! price scale of their weekend. Yahoo rescales its whole history when
//! a stock splits, so reported opens are multiplied back by the
//! cumulative ratio of any splits dated *after* the target date. Every
//! such adjustment is disclosed in the report.

use std::collections::{BTreeMap, BTreeSet, HashMap};
use std::error::Error;
use std::time::{SystemTime, UNIX_EPOCH};

/// Days-from-civil / civil-from-days (Howard Hinnant's algorithms) —
/// enough calendar math to avoid a chrono dependency.
pub fn days_from_civil(y: i64, m: u32, d: u32) -> i64 {
    let y = if m <= 2 { y - 1 } else { y };
    let era = if y >= 0 { y } else { y - 399 } / 400;
    let yoe = (y - era * 400) as u64;
    let mp = if m > 2 { m - 3 } else { m + 9 } as u64;
    let doy = (153 * mp + 2) / 5 + d as u64 - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    era * 146097 + doe as i64 - 719468
}

pub fn civil_from_days(z: i64) -> (i64, u32, u32) {
    let z = z + 719468;
    let era = if z >= 0 { z } else { z - 146096 } / 146097;
    let doe = (z - era * 146097) as u64;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let y = yoe as i64 + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = (doy - (153 * mp + 2) / 5 + 1) as u32;
    let m = if mp < 10 { mp + 3 } else { mp - 9 } as u32;
    (y + if m <= 2 { 1 } else { 0 }, m, d)
}

fn parse_iso_date(s: &str) -> Result<(i64, u32, u32), Box<dyn Error>> {
    let parts: Vec<&str> = s.split('-').collect();
    if parts.len() != 3 {
        return Err(format!("bad date {s:?} (want YYYY-MM-DD)").into());
    }
    Ok((parts[0].parse()?, parts[1].parse()?, parts[2].parse()?))
}

fn iso(y: i64, m: u32, d: u32) -> String {
    format!("{y:04}-{m:02}-{d:02}")
}

struct SymbolSeries {
    /// iso date → raw reported open (Yahoo's current scale).
    opens: BTreeMap<String, f64>,
    /// (iso split date, numerator/denominator ratio).
    splits: Vec<(String, f64)>,
}

pub struct Truth {
    series: HashMap<String, SymbolSeries>,
}

pub struct Open {
    pub value: f64,
    /// Cumulative split factor applied to renormalise to the as-traded
    /// scale of the target date (1.0 = untouched).
    pub split_factor: f64,
}

impl Truth {
    /// Fetch daily bars for every symbol, spanning `from_date` → now.
    pub fn fetch(symbols: &BTreeSet<String>, from_date: &str) -> Result<Truth, Box<dyn Error>> {
        let (y, m, d) = parse_iso_date(from_date)?;
        let period1 = (days_from_civil(y, m, d) - 5) * 86_400;
        let period2 = SystemTime::now()
            .duration_since(UNIX_EPOCH)?
            .as_secs() as i64
            + 86_400;
        let client = crate::http::client()?;
        let mut series = HashMap::new();
        for (i, sym) in symbols.iter().enumerate() {
            if i > 0 {
                // Courtesy pacing — Yahoo 429s bursty anonymous clients.
                std::thread::sleep(std::time::Duration::from_millis(300));
            }
            let url = format!(
                "https://query2.finance.yahoo.com/v8/finance/chart/{sym}?period1={period1}&period2={period2}&interval=1d&events=splits"
            );
            let mut attempt = 0usize;
            let v: serde_json::Value = loop {
                attempt += 1;
                let resp = client.get(&url).send()?;
                let status = resp.status();
                if status.is_success() {
                    break resp.json()?;
                }
                let retryable = status.as_u16() == 429 || status.is_server_error();
                if !retryable || attempt > 3 {
                    return Err(format!("Yahoo chart {sym}: HTTP {status}").into());
                }
                let wait = [5u64, 15, 30][attempt - 1];
                eprintln!("Yahoo chart {sym}: HTTP {status} — retrying in {wait}s …");
                std::thread::sleep(std::time::Duration::from_secs(wait));
            };
            series.insert(sym.clone(), parse_chart(sym, &v)?);
        }
        Ok(Truth { series })
    }

    /// Regular-session open for `symbol` on `date` (iso), renormalised
    /// to the as-traded scale of that date.
    pub fn open(&self, symbol: &str, date: &str) -> Option<Open> {
        let s = self.series.get(symbol)?;
        let raw = *s.opens.get(date)?;
        let factor: f64 = s
            .splits
            .iter()
            .filter(|(split_date, _)| split_date.as_str() > date)
            .map(|(_, ratio)| ratio)
            .product();
        Some(Open {
            value: raw * factor,
            split_factor: factor,
        })
    }
}

fn parse_chart(sym: &str, v: &serde_json::Value) -> Result<SymbolSeries, Box<dyn Error>> {
    if let Some(err) = v.pointer("/chart/error").filter(|e| !e.is_null()) {
        return Err(format!("Yahoo chart {sym}: {err}").into());
    }
    let result = v
        .pointer("/chart/result/0")
        .ok_or_else(|| format!("Yahoo chart {sym}: empty result"))?;
    let gmtoffset = result
        .pointer("/meta/gmtoffset")
        .and_then(|g| g.as_i64())
        .unwrap_or(0);
    let timestamps = result
        .pointer("/timestamp")
        .and_then(|t| t.as_array())
        .ok_or_else(|| format!("Yahoo chart {sym}: no timestamps"))?;
    let opens = result
        .pointer("/indicators/quote/0/open")
        .and_then(|o| o.as_array())
        .ok_or_else(|| format!("Yahoo chart {sym}: no opens"))?;

    let mut open_map = BTreeMap::new();
    for (ts, open) in timestamps.iter().zip(opens.iter()) {
        let (Some(ts), Some(open)) = (ts.as_i64(), open.as_f64()) else {
            continue;
        };
        let (y, m, d) = civil_from_days((ts + gmtoffset).div_euclid(86_400));
        open_map.insert(iso(y, m, d), open);
    }

    let mut splits = Vec::new();
    if let Some(map) = result.pointer("/events/splits").and_then(|s| s.as_object()) {
        for split in map.values() {
            let (Some(ts), Some(num), Some(den)) = (
                split.get("date").and_then(|x| x.as_i64()),
                split.get("numerator").and_then(|x| x.as_f64()),
                split.get("denominator").and_then(|x| x.as_f64()),
            ) else {
                continue;
            };
            if den == 0.0 {
                continue;
            }
            let (y, m, d) = civil_from_days((ts + gmtoffset).div_euclid(86_400));
            splits.push((iso(y, m, d), num / den));
        }
    }
    splits.sort_by(|a, b| a.0.cmp(&b.0));
    Ok(SymbolSeries {
        opens: open_map,
        splits,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn civil_round_trip() {
        for (y, m, d) in [(1970, 1, 1), (2026, 5, 4), (2026, 7, 20), (2000, 2, 29)] {
            let days = days_from_civil(y, m, d);
            assert_eq!(civil_from_days(days), (y, m, d));
        }
        assert_eq!(days_from_civil(1970, 1, 1), 0);
    }
}
