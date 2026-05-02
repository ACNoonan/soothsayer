//! On-chain account types for the BandAMM.
//!
//! Layout principles mirror `soothsayer-oracle-program::state`:
//! - 8-byte alignment with explicit `_padN` reserved bytes.
//! - All fee parameters expressed as integer basis points or i64 fixed-point —
//!   never floats. No host/BPF drift.
//! - Schema versioned so a future hard layout change can be detected by clients
//!   without guessing.

use anchor_lang::prelude::*;

/// Per-pool PDA. Seeded `[b"band_amm_pool", base_mint, quote_mint]`.
///
/// One pool per (base, quote) directed pair. The base/quote ordering is
/// caller-determined at `initialize_pool` and locked thereafter; Jupiter / UI
/// clients should canonicalise.
#[account]
#[derive(InitSpace)]
pub struct BandAmmPool {
    /// Schema version. Bumps on layout change. Current: 1.
    pub version: u8,
    /// 1 if swap + deposit are paused (authority-triggered).
    pub paused: u8,
    /// Bump for this PDA. Stored to avoid re-derivation in CPIs.
    pub pool_bump: u8,
    /// Bump for the LP mint PDA.
    pub lp_mint_bump: u8,
    /// Bump for the base vault token account PDA.
    pub base_vault_bump: u8,
    /// Bump for the quote vault token account PDA.
    pub quote_vault_bump: u8,
    pub _pad0: [u8; 2],

    /// Authority that can pause / set fee params. Multisig in production.
    pub authority: Pubkey,

    /// SPL mints. Locked at init.
    pub base_mint: Pubkey,
    pub quote_mint: Pubkey,

    /// Vault token accounts owned by this pool PDA.
    pub base_vault: Pubkey,
    pub quote_vault: Pubkey,

    /// LP mint owned by this pool PDA.
    pub lp_mint: Pubkey,

    /// Soothsayer `PriceUpdate` PDA the pool reads. Locked at init —
    /// mismatched accounts at swap time return `WrongPriceUpdate`.
    pub price_update: Pubkey,

    /// In-band swap fee (basis points, 5 = 5 bps).
    pub fee_bps_in: u16,
    /// Outside-band surcharge slope (bps per unit of d/w). 16-bit so the
    /// schedule has enough resolution for tail charges.
    pub fee_alpha_out_bps: u16,
    /// Outside-band cap on `clamp(d/w, 0, w_max)` — the saturation point of the
    /// surcharge ramp. Encoded as bps of width units (10000 = 1.0x band width).
    pub fee_w_max_bps: u16,
    /// Maximum band staleness tolerated at swap time (seconds). Default 60.
    pub max_band_staleness_secs: u32,
    pub _pad1: [u8; 2],

    /// Cumulative fees accrued in base + quote (informational; LPs realise via
    /// reserve growth on withdraw, not via a separate claim path).
    pub cumulative_fees_base: u64,
    pub cumulative_fees_quote: u64,
    pub cumulative_swaps: u64,

    pub _pad2: [u8; 16],
}

/// Schema version. Bump on any on-wire layout change.
pub const BAND_AMM_POOL_VERSION: u8 = 1;

/// Defaults. Tuneable post-deploy by `set_fee_params`.
pub const DEFAULT_FEE_BPS_IN: u16 = 5; // 5 bps in-band
pub const DEFAULT_FEE_ALPHA_OUT_BPS: u16 = 30; // surcharge slope per d/w unit
pub const DEFAULT_FEE_W_MAX_BPS: u16 = 10_000; // saturate at d == w
pub const DEFAULT_MAX_BAND_STALENESS_SECS: u32 = 60;
