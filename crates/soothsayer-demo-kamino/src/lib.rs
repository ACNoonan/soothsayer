//! Reference Kamino-fork lending logic — consumes a Soothsayer `PriceBand`.
//!
//! **Purpose.** This crate is a teaching artifact, not production lending
//! code. It demonstrates how a Kamino-style lending protocol's LTV and
//! liquidation-threshold decisions change when the oracle input is a
//! calibrated empirical band (Soothsayer) vs. a stylized flat-haircut
//! baseline inspired by earlier Kamino-comparison scaffolding.
//!
//! **Pitch one-liner:** *"The live reserve buffer is narrow; Soothsayer makes
//! the weekend uncertainty around that buffer explicit."* See
//! `reports/v1b_decision.md` and `07.1 - Deep Research Output v2.md` Topic 2.
//!
//! ## The decision model
//!
//! For each open borrow position, the protocol has:
//!
//! - `debt_value` — USDC-denominated outstanding debt.
//! - `collateral_qty` — units of the asset held as collateral.
//! - A `PriceBand` from Soothsayer with `(point, lower, upper, regime, receipt)`.
//! - Three static governance parameters: max-LTV-at-origination, liquidation
//!   threshold, and regime multipliers.
//!
//! The protocol values collateral at the **lower bound** (not the point) —
//! the conservative reading that survives a benign band-to-spot reversion.
//! The liquidation threshold is held flat across regimes (no double-demote);
//! all regime-awareness flows through the band's lower bound. The OOS
//! protocol-comparison bootstrap (`reports/tables/protocol_compare_*.csv`)
//! confirmed that demoting the threshold *on top of* a regime-aware band
//! more than doubles pooled expected loss without measurable miss-rate
//! benefit. The `RegimeMultipliers` field is retained so a consumer can opt
//! back into threshold demotion explicitly, but defaults are 1.0 across
//! regimes.
//!
//! Decision categories:
//!
//! - `Safe` — current LTV is well below liquidation threshold; no action.
//! - `Caution` — LTV is between max-LTV-at-origination and the liquidation
//!   threshold. The protocol prevents new borrows against this position
//!   (or notifies the borrower), but doesn't liquidate.
//! - `Liquidate` — LTV ≥ regime-adjusted liquidation threshold.
//!
//! ## What this demo does NOT model
//!
//! - Interest accrual between blocks
//! - Liquidation bonuses / kickers
//! - Bad-debt socialization / insurance fund
//! - Market-impact haircut for large liquidation sizes (per Pyth's "liquidity
//!   oracle" idea from `07.1` Topic 2 — a real extension but out of scope for
//!   a pitch demo; the Soothsayer calibration surface is the moat, not the
//!   market-impact layer on top)
//! - Interest-bearing / rebasing collateral (Token-2022 `ScaledUiAmountConfig`
//!   — handled at a separate layer, not in the LTV calc)

#![forbid(unsafe_code)]

use soothsayer_consumer::{PriceBand, Regime};
use thiserror::Error;

/// Outcome of evaluating a single borrow position against a price band.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum LendingDecision {
    /// Position is well within the regime-adjusted safety zone.
    Safe,
    /// Position is above the new-borrow threshold but not yet liquidatable.
    /// New borrows against this position are blocked.
    Caution,
    /// Position is at or beyond the regime-adjusted liquidation threshold.
    /// Eligible for liquidation this block.
    Liquidate,
}

/// Governance parameters. In a real protocol these live in a `LendingMarket`
/// PDA and are governance-mutable.
#[derive(Clone, Debug)]
pub struct LendingParams {
    /// Maximum LTV at new-borrow origination. Below this, borrows are allowed;
    /// between this and `liquidation_threshold`, existing positions continue
    /// but no new borrows can be opened against the account.
    ///
    /// Default: 0.75 (75% LTV).
    pub max_ltv_at_origination: f64,
    /// LTV at or above which liquidation is triggered. Default: 0.85.
    pub liquidation_threshold: f64,
    /// Multipliers that demote the liquidation threshold in stressed regimes.
    /// `threshold_effective = liquidation_threshold × multiplier[regime]`.
    pub regime_multipliers: RegimeMultipliers,
    /// If the oracle receipt shows the calibration buffer was saturated at
    /// the grid ceiling (e.g. target=0.99 clipped to claim=0.995), force
    /// Caution-or-worse on any position — the model is telling us it can't
    /// honor the requested coverage and the consumer should tighten.
    pub treat_clipped_as_caution: bool,
}

/// Per-regime multiplier on the liquidation threshold. Values < 1.0 tighten
/// the safety zone; = 1.0 passes the base threshold through.
///
/// Defaults are 1.0 across all regimes — threshold demotion is OFF by default.
/// The OOS protocol-comparison bootstrap (`reports/tables/protocol_compare_*`)
/// showed that demoting the threshold on top of a regime-aware band more than
/// doubles pooled expected loss with no miss-rate offset (Case B at t=0.85
/// runs EL ≈ 0.135 vs Case A at the same target ≈ 0.060; the false-positive
/// liquidation rate jumps ~15pp while miss rate is unchanged within noise).
/// All regime-awareness now flows through the band's lower bound. A consumer
/// who wants explicit threshold demotion can override these multipliers.
#[derive(Clone, Copy, Debug)]
pub struct RegimeMultipliers {
    pub normal: f64,
    pub long_weekend: f64,
    pub high_vol: f64,
}

impl RegimeMultipliers {
    pub fn get(&self, regime: Regime) -> f64 {
        match regime {
            Regime::Normal => self.normal,
            Regime::LongWeekend => self.long_weekend,
            // Shock regime isn't used by the Oracle today, but a consumer that
            // sees it should treat it at least as tightly as high_vol.
            Regime::HighVol | Regime::ShockFlagged => self.high_vol,
        }
    }
}

impl Default for RegimeMultipliers {
    fn default() -> Self {
        Self {
            normal: 1.00,
            long_weekend: 1.00,
            high_vol: 1.00,
        }
    }
}

impl Default for LendingParams {
    fn default() -> Self {
        Self {
            max_ltv_at_origination: 0.75,
            liquidation_threshold: 0.85,
            regime_multipliers: RegimeMultipliers::default(),
            treat_clipped_as_caution: true,
        }
    }
}

/// A single borrow position.
#[derive(Clone, Debug)]
pub struct Position {
    /// USDC-denominated outstanding debt.
    pub debt_usdc: f64,
    /// Units of the underlying asset held as collateral.
    pub collateral_qty: f64,
}

/// Structured evaluation output — the numbers that drive the decision, for
/// pitch-deck screenshots and audit logs.
#[derive(Clone, Debug)]
pub struct Evaluation {
    pub decision: LendingDecision,
    /// Collateral value computed at the lower bound (conservative reading).
    pub collateral_value_conservative: f64,
    /// Collateral value computed at the point estimate (for comparison only;
    /// a risk-aware protocol does NOT make decisions off this).
    pub collateral_value_point: f64,
    /// Current LTV = debt / conservative_collateral_value.
    pub current_ltv: f64,
    /// Max LTV allowed at origination (below this, new borrows allowed).
    pub max_ltv_at_origination: f64,
    /// Liquidation threshold AFTER regime multiplier applied.
    pub effective_liquidation_threshold: f64,
    /// Sharpness (half-width) of the consumed band, in bps of point. Useful
    /// for showing "how much tighter is the Soothsayer band".
    pub band_half_width_bps: f64,
}

/// Error type for evaluation edge cases.
#[derive(Debug, Error, Clone, Copy, PartialEq)]
pub enum EvalError {
    #[error("band invariants invalid")]
    BandInvalid,
    #[error("zero or negative collateral quantity")]
    NoCollateral,
    #[error("zero or negative collateral value at lower bound")]
    ZeroValueCollateral,
}

/// Evaluate a single position against a Soothsayer `PriceBand`.
pub fn evaluate(
    band: &PriceBand,
    position: &Position,
    params: &LendingParams,
) -> Result<Evaluation, EvalError> {
    band.validate_invariants().map_err(|_| EvalError::BandInvalid)?;
    if position.collateral_qty <= 0.0 {
        return Err(EvalError::NoCollateral);
    }

    let regime = Regime::from_code(band.regime_code).unwrap_or(Regime::HighVol);

    let lower = band.lower_f64();
    let point = band.point_f64();

    let collateral_value_conservative = lower * position.collateral_qty;
    let collateral_value_point = point * position.collateral_qty;

    if collateral_value_conservative <= 0.0 {
        return Err(EvalError::ZeroValueCollateral);
    }

    let current_ltv = position.debt_usdc / collateral_value_conservative;

    let regime_mult = params.regime_multipliers.get(regime);
    let effective_threshold = params.liquidation_threshold * regime_mult;

    // Decision ladder:
    let mut decision = if current_ltv >= effective_threshold {
        LendingDecision::Liquidate
    } else if current_ltv >= params.max_ltv_at_origination {
        LendingDecision::Caution
    } else {
        LendingDecision::Safe
    };

    // If the band was produced at a saturated-grid claim (receipt says
    // we couldn't honor the requested coverage), take the conservative
    // side: Safe → Caution. Liquidate stays Liquidate.
    if params.treat_clipped_as_caution && decision == LendingDecision::Safe {
        // Heuristic: if claimed_served_bps is at the grid ceiling (9950 = 99.5%),
        // treat the band's claim as saturated. This matches the Python
        // Oracle's grid ceiling (see MAX_SERVED_TARGET = 0.995).
        if band.claimed_served_bps >= 9950 {
            decision = LendingDecision::Caution;
        }
    }

    let band_half_width_bps = band.half_width_bps();

    Ok(Evaluation {
        decision,
        collateral_value_conservative,
        collateral_value_point,
        current_ltv,
        max_ltv_at_origination: params.max_ltv_at_origination,
        effective_liquidation_threshold: effective_threshold,
        band_half_width_bps,
    })
}

/// A legacy flat-band baseline kept for side-by-side comparison with earlier
/// protocol-policy scaffolding.
///
/// Model: the protocol accepts the oracle's point and applies a flat
/// `deviation_bps` haircut during closed-market windows. `lower = point *
/// (1 - bps/10000)`, `upper = point * (1 + bps/10000)`. No regime awareness,
/// no empirical calibration — just a single stylized parameter per asset.
pub fn flat_gov_band_from_point(point: f64, deviation_bps: u16) -> (f64, f64) {
    let frac = deviation_bps as f64 / 10_000.0;
    (point * (1.0 - frac), point * (1.0 + frac))
}

/// Evaluate a position using a flat-governance-band model instead of a
/// Soothsayer calibrated band. The contrast between this and [`evaluate`] is
/// the pitch's core comparison.
pub fn evaluate_with_flat_band(
    point: f64,
    deviation_bps: u16,
    position: &Position,
    params: &LendingParams,
) -> Result<Evaluation, EvalError> {
    if position.collateral_qty <= 0.0 {
        return Err(EvalError::NoCollateral);
    }
    let (lower, _upper) = flat_gov_band_from_point(point, deviation_bps);
    let collateral_value_conservative = lower * position.collateral_qty;
    let collateral_value_point = point * position.collateral_qty;

    if collateral_value_conservative <= 0.0 {
        return Err(EvalError::ZeroValueCollateral);
    }

    let current_ltv = position.debt_usdc / collateral_value_conservative;

    // Flat band — no regime awareness by construction.
    let effective_threshold = params.liquidation_threshold;

    let decision = if current_ltv >= effective_threshold {
        LendingDecision::Liquidate
    } else if current_ltv >= params.max_ltv_at_origination {
        LendingDecision::Caution
    } else {
        LendingDecision::Safe
    };

    let half_width_bps = if point == 0.0 {
        0.0
    } else {
        deviation_bps as f64 // by definition, deviation_bps IS the half-width in bps
    };

    Ok(Evaluation {
        decision,
        collateral_value_conservative,
        collateral_value_point,
        current_ltv,
        max_ltv_at_origination: params.max_ltv_at_origination,
        effective_liquidation_threshold: effective_threshold,
        band_half_width_bps: half_width_bps,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use soothsayer_consumer::{
        FORECASTER_F1_EMP_REGIME, PROFILE_LENDING, REGIME_HIGH_VOL, REGIME_NORMAL,
    };

    /// Build a synthetic PriceBand with exponent = -8 (standard Soothsayer scale).
    fn make_band(
        point: f64,
        lower: f64,
        upper: f64,
        regime: u8,
        claim_bps: u16,
    ) -> PriceBand {
        let to_fixed = |v: f64| (v * 1e8) as i64;
        let mut symbol = [0u8; 16];
        symbol[..3].copy_from_slice(b"SPY");
        PriceBand {
            version: 1,
            regime_code: regime,
            forecaster_code: FORECASTER_F1_EMP_REGIME,
            exponent: -8,
            profile_code: PROFILE_LENDING,
            target_coverage_bps: 9500,
            claimed_served_bps: claim_bps,
            buffer_applied_bps: 250,
            symbol,
            point: to_fixed(point),
            lower: to_fixed(lower),
            upper: to_fixed(upper),
            fri_close: to_fixed(point),
            fri_ts: 0,
            publish_ts: 0,
            publish_slot: 0,
            signer: [0; 32],
            signer_epoch: 1,
        }
    }

    #[test]
    fn safe_position_normal_regime() {
        // Band at $700, ±1% → lower $693. Collateral 10 @ $693 = $6930.
        // Debt $3000 → LTV = 43.3%. Well below max-LTV 75%.
        let band = make_band(700.0, 693.0, 707.0, REGIME_NORMAL, 9750);
        let pos = Position { debt_usdc: 3000.0, collateral_qty: 10.0 };
        let eval = evaluate(&band, &pos, &LendingParams::default()).unwrap();
        assert_eq!(eval.decision, LendingDecision::Safe);
        assert!((eval.current_ltv - (3000.0 / 6930.0)).abs() < 1e-9);
        // Liquidation threshold = 0.85 × 1.00 (normal) = 0.85
        assert!((eval.effective_liquidation_threshold - 0.85).abs() < 1e-9);
    }

    #[test]
    fn caution_position_between_origination_and_liquidation() {
        // Debt $5600 vs collateral-at-lower $6930 → LTV = 80.8% (between 75 and 85).
        let band = make_band(700.0, 693.0, 707.0, REGIME_NORMAL, 9750);
        let pos = Position { debt_usdc: 5600.0, collateral_qty: 10.0 };
        let eval = evaluate(&band, &pos, &LendingParams::default()).unwrap();
        assert_eq!(eval.decision, LendingDecision::Caution);
    }

    #[test]
    fn liquidate_position_above_threshold() {
        // Debt $6000 vs collateral-at-lower $6930 → LTV = 86.6% (≥ 85 threshold).
        let band = make_band(700.0, 693.0, 707.0, REGIME_NORMAL, 9750);
        let pos = Position { debt_usdc: 6000.0, collateral_qty: 10.0 };
        let eval = evaluate(&band, &pos, &LendingParams::default()).unwrap();
        assert_eq!(eval.decision, LendingDecision::Liquidate);
    }

    #[test]
    fn default_threshold_is_flat_across_regimes() {
        // Regression: with shipping defaults (RegimeMultipliers all 1.0), the
        // effective liquidation threshold is identical across regimes. This is
        // the post-2026-04-25 behavior — Case A on the Kamino-fork demo. The
        // earlier double-demote (Case B) was retired after the OOS bootstrap
        // showed it inflated expected loss by ~75% pooled.
        let band_normal = make_band(700.0, 693.0, 707.0, REGIME_NORMAL, 9750);
        let band_highvol = make_band(700.0, 693.0, 707.0, REGIME_HIGH_VOL, 9900);
        let pos = Position { debt_usdc: 5200.0, collateral_qty: 10.0 };
        let eval_n = evaluate(&band_normal, &pos, &LendingParams::default()).unwrap();
        let eval_h = evaluate(&band_highvol, &pos, &LendingParams::default()).unwrap();
        assert_eq!(eval_n.effective_liquidation_threshold, 0.85);
        assert_eq!(eval_h.effective_liquidation_threshold, 0.85);
        // Same LTV → same decision in both regimes under flat threshold.
        assert_eq!(eval_n.decision, eval_h.decision);
    }

    #[test]
    fn opt_in_threshold_demote_still_works() {
        // The mechanism remains available for consumers who explicitly request
        // it. Pass a non-1.0 multiplier and confirm the threshold drops.
        let band_highvol = make_band(700.0, 693.0, 707.0, REGIME_HIGH_VOL, 9900);
        let pos = Position { debt_usdc: 5200.0, collateral_qty: 10.0 };
        let mut params = LendingParams::default();
        params.regime_multipliers = RegimeMultipliers {
            normal: 1.00,
            long_weekend: 0.95,
            high_vol: 0.85,
        };
        let eval = evaluate(&band_highvol, &pos, &params).unwrap();
        // 0.85 × 0.85 = 0.7225. LTV 5200/6930 ≈ 0.750 > 0.7225 → liquidate.
        assert_eq!(eval.decision, LendingDecision::Liquidate);
        assert!((eval.effective_liquidation_threshold - 0.7225).abs() < 1e-9);
    }

    #[test]
    fn clipped_band_forces_caution() {
        // Safe-by-LTV position but claimed_served_bps saturated at grid ceiling.
        let band = make_band(700.0, 693.0, 707.0, REGIME_NORMAL, 9950);
        let pos = Position { debt_usdc: 1000.0, collateral_qty: 10.0 };
        let eval = evaluate(&band, &pos, &LendingParams::default()).unwrap();
        assert_eq!(eval.decision, LendingDecision::Caution);
    }

    #[test]
    fn flat_gov_band_vs_empirical_side_by_side() {
        // A high-vol weekend comparison where both bands fire Liquidate but for
        // different reasons. Setup: point price $700 at Friday close.
        // - Legacy flat-band baseline: ±300 bps = lower $679. Collateral $6790 → LTV 88%. LIQUIDATES.
        // - Soothsayer high-vol band: point $700, lower $665 (wider than flat), claim 0.99.
        //     Collateral $6650 → LTV 90%. LIQUIDATES at the flat 0.85 threshold.
        // The Soothsayer reading is more conservative because the wider lower
        // bound reflects the genuine regime risk, even with the same threshold.
        let pos = Position { debt_usdc: 6000.0, collateral_qty: 10.0 };
        let params = LendingParams::default();

        let kamino_eval =
            evaluate_with_flat_band(700.0, 300, &pos, &params).unwrap();
        let soothsayer_band = make_band(700.0, 665.0, 735.0, REGIME_HIGH_VOL, 9900);
        let soothsayer_eval = evaluate(&soothsayer_band, &pos, &params).unwrap();

        // Both see this as a liquidate under different thresholds.
        assert_eq!(kamino_eval.decision, LendingDecision::Liquidate);
        assert_eq!(soothsayer_eval.decision, LendingDecision::Liquidate);

        // But the soothsayer LTV reading (at its conservative lower bound)
        // is different: wider band → lower collateral value → higher LTV.
        assert!(soothsayer_eval.current_ltv > kamino_eval.current_ltv);

        // And Soothsayer's band in high_vol is materially wider than the legacy fixed 300 bps
        // baseline, reflecting the genuine regime risk rather than a one-number shortcut.
        assert!(soothsayer_eval.band_half_width_bps > kamino_eval.band_half_width_bps);
    }

    #[test]
    fn caution_threshold_is_symmetric_across_regimes() {
        // Max-LTV-at-origination is a static governance parameter, not regime-adjusted.
        // Only liquidation_threshold gets the regime multiplier.
        let band_h = make_band(700.0, 693.0, 707.0, REGIME_HIGH_VOL, 9900);
        let eval = evaluate(
            &band_h,
            &Position { debt_usdc: 1.0, collateral_qty: 10.0 },
            &LendingParams::default(),
        )
        .unwrap();
        assert_eq!(eval.max_ltv_at_origination, 0.75);
    }
}
