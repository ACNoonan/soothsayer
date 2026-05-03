//! JSON artefact ledger.
//!
//! Persistent record of every devnet thing the CLI creates: mints, pool
//! PDAs, published bands, and the running list of demo swaps. Lets the
//! `seed-all` pipeline be idempotent across reruns and gives the deck /
//! README a single source-of-truth file to link from.

use std::{collections::BTreeMap, fs, path::Path};

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use solana_sdk::pubkey::Pubkey;

use crate::oracle_ix::BandRecord;

#[derive(Default, Serialize, Deserialize, Clone, Debug)]
pub struct Artefact {
    pub rpc_url: Option<String>,
    pub wallet: Option<String>,
    pub band_amm_program: Option<String>,
    pub oracle_program: Option<String>,

    #[serde(default)]
    pub mints: BTreeMap<String, MintRecord>,

    #[serde(default)]
    pub bands: BTreeMap<String, BandRecord>,

    #[serde(default)]
    pub pools: BTreeMap<String, PoolRecord>,

    #[serde(default)]
    pub swaps: Vec<SwapRecord>,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct MintRecord {
    pub label: String,
    pub pubkey: String,
    pub decimals: u8,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct PoolRecord {
    pub label: String,
    pub symbol: String,
    pub base_mint: String,
    pub quote_mint: String,
    pub pool: String,
    pub lp_mint: String,
    pub base_vault: String,
    pub quote_vault: String,
    pub price_update: String,
    #[serde(default)]
    pub deposited: bool,
}

// Manual `Default` so PoolRecord can be merged from a partial without
// touching the `deposited` flag.
impl Default for PoolRecord {
    fn default() -> Self {
        PoolRecord {
            label: String::new(),
            symbol: String::new(),
            base_mint: String::new(),
            quote_mint: String::new(),
            pool: String::new(),
            lp_mint: String::new(),
            base_vault: String::new(),
            quote_vault: String::new(),
            price_update: String::new(),
            deposited: false,
        }
    }
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct SwapRecord {
    pub pool_label: String,
    pub signature: String,
    pub amount_in_atoms: u64,
    pub side_base_in: bool,
    pub explorer_url: String,
    pub ts: i64,
}

impl Artefact {
    pub fn load_or_init(path: &Path) -> Result<Self> {
        if !path.exists() {
            return Ok(Self::default());
        }
        let raw = fs::read_to_string(path).with_context(|| format!("read {}", path.display()))?;
        let parsed: Artefact = serde_json::from_str(&raw)
            .with_context(|| format!("parse JSON {}", path.display()))?;
        Ok(parsed)
    }

    pub fn save(&self, path: &Path) -> Result<()> {
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent).ok();
        }
        let pretty = serde_json::to_string_pretty(self).context("serialize artefact JSON")?;
        fs::write(path, pretty).with_context(|| format!("write {}", path.display()))?;
        Ok(())
    }

    pub fn set_mint(&mut self, key: &str, label: &str, pubkey: &Pubkey, decimals: u8) {
        self.mints.insert(
            key.to_string(),
            MintRecord {
                label: label.to_string(),
                pubkey: pubkey.to_string(),
                decimals,
            },
        );
    }

    pub fn mint(&self, key: &str) -> Option<&MintRecord> {
        self.mints.get(key)
    }
    pub fn mint_pubkey(&self, key: &str) -> Option<Pubkey> {
        self.mints.get(key).and_then(|m| m.pubkey.parse().ok())
    }
    pub fn mint_for_pubkey(&self, pubkey: &str) -> Option<&MintRecord> {
        self.mints.values().find(|m| m.pubkey == pubkey)
    }

    pub fn set_band(&mut self, symbol: &str, record: BandRecord) {
        self.bands.insert(symbol.to_string(), record);
    }

    pub fn upsert_pool(&mut self, label: &str, record: PoolRecord) {
        let prev = self.pools.get(label).cloned();
        let merged = PoolRecord {
            deposited: prev.map(|p| p.deposited).unwrap_or(false),
            ..record
        };
        self.pools.insert(label.to_string(), merged);
    }

    pub fn pool(&self, label: &str) -> Option<&PoolRecord> {
        self.pools.get(label)
    }

    pub fn mark_deposited(&mut self, label: &str, deposited: bool) {
        if let Some(p) = self.pools.get_mut(label) {
            p.deposited = deposited;
        }
    }

    pub fn append_swap(
        &mut self,
        pool_label: &str,
        signature: &str,
        amount_in_atoms: u64,
        side_base_in: bool,
    ) {
        self.swaps.push(SwapRecord {
            pool_label: pool_label.to_string(),
            signature: signature.to_string(),
            amount_in_atoms,
            side_base_in,
            explorer_url: format!(
                "https://explorer.solana.com/tx/{signature}?cluster=devnet"
            ),
            ts: chrono::Utc::now().timestamp(),
        });
    }
}
