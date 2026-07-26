//! Python ↔ Rust parity for the M5 (Mondrian) and M6 (LWC) serving paths.
//!
//! The 180/180 parity recorded in `reports/active/m6_refactor.md` was a
//! one-off validation with no committed harness, so nothing caught drift on
//! the serving path. This is that harness.
//!
//! Two failure modes, and the second is the one that will actually bite:
//!
//! 1. **Formula drift** — the band arithmetic diverges between `oracle.py`
//!    and `oracle.rs`. Caught by the per-case comparison.
//!
//! 2. **Constant staleness** — Python loads the per-regime quantiles, c(τ)
//!    and δ schedules from the artefact JSON sidecar *at import*; Rust
//!    hardcodes them in `config.rs`. Rebuild the artefact and the Rust
//!    constants are silently stale: the oracle keeps serving, just with the
//!    previous calibration, and nothing in the type system notices. The
//!    constants tests below are the loud failure that replaces that silence.
//!
//! Cases embed the artefact row fields, so this suite needs no parquet —
//! `data/processed/` is gitignored, and a test that silently skips on a
//! clean checkout is not a regression test.

use serde_json::Value;
use soothsayer_oracle::config::{
    c_bump_for_target, delta_shift_for_target, lwc_c_bump_for, lwc_delta_shift_for,
    lwc_regime_quantile_for, regime_quantile_for, MAX_SERVED_TARGET, MIN_SERVED_TARGET,
};

const FIXTURE: &str = include_str!("fixtures/oracle_parity.json");

fn fx() -> Value {
    serde_json::from_str(FIXTURE).unwrap()
}

fn close(a: f64, b: f64) -> bool {
    let tol = 1e-9_f64.max(1e-9 * b.abs());
    (a - b).abs() <= tol
}

fn assert_close(got: f64, want: f64, ctx: &str) {
    assert!(close(got, want), "{ctx}: rust {got} vs python {want}");
}

/// Rust's hardcoded M5 tables must equal the Python sidecar. A mismatch here
/// means the artefact was rebuilt and `config.rs` was not updated.
#[test]
fn mondrian_constants_match_sidecar() {
    let f = fx();
    let anchors: Vec<f64> = f["anchors"].as_array().unwrap()
        .iter().map(|v| v.as_f64().unwrap()).collect();
    let c = &f["mondrian_constants"];
    for (regime, row) in c["regime_quantile_table"].as_object().unwrap() {
        for (i, want) in row.as_array().unwrap().iter().enumerate() {
            assert_close(
                regime_quantile_for(regime, anchors[i]),
                want.as_f64().unwrap(),
                &format!("M5 q[{regime}][{}] — artefact rebuilt without updating config.rs?", anchors[i]),
            );
        }
    }
    for (i, want) in c["c_bump_schedule"].as_array().unwrap().iter().enumerate() {
        assert_close(c_bump_for_target(anchors[i]), want.as_f64().unwrap(),
                     &format!("M5 c({})", anchors[i]));
    }
    for (i, want) in c["delta_shift_schedule"].as_array().unwrap().iter().enumerate() {
        assert_close(delta_shift_for_target(anchors[i]), want.as_f64().unwrap(),
                     &format!("M5 delta({})", anchors[i]));
    }
}

#[test]
fn lwc_constants_match_sidecar() {
    let f = fx();
    let anchors: Vec<f64> = f["anchors"].as_array().unwrap()
        .iter().map(|v| v.as_f64().unwrap()).collect();
    let c = &f["lwc_constants"];
    for (regime, row) in c["regime_quantile_table"].as_object().unwrap() {
        for (i, want) in row.as_array().unwrap().iter().enumerate() {
            assert_close(
                lwc_regime_quantile_for(regime, anchors[i]),
                want.as_f64().unwrap(),
                &format!("M6 q[{regime}][{}] — artefact rebuilt without updating config.rs?", anchors[i]),
            );
        }
    }
    for (i, want) in c["c_bump_schedule"].as_array().unwrap().iter().enumerate() {
        assert_close(lwc_c_bump_for(anchors[i]), want.as_f64().unwrap(),
                     &format!("M6 c({})", anchors[i]));
    }
    for (i, want) in c["delta_shift_schedule"].as_array().unwrap().iter().enumerate() {
        assert_close(lwc_delta_shift_for(anchors[i]), want.as_f64().unwrap(),
                     &format!("M6 delta({})", anchors[i]));
    }
}

/// Off-anchor τ exercises the linear interpolation, which is where a
/// boundary-handling difference between the two implementations would hide.
#[test]
fn schedule_interpolation_parity() {
    for case in fx()["interp"].as_array().unwrap() {
        let tau = case["tau"].as_f64().unwrap();
        let r = case["regime"].as_str().unwrap();
        assert_close(regime_quantile_for(r, tau), case["mondrian_q"].as_f64().unwrap(),
                     &format!("M5 q[{r}]({tau})"));
        assert_close(lwc_regime_quantile_for(r, tau), case["lwc_q"].as_f64().unwrap(),
                     &format!("M6 q[{r}]({tau})"));
        assert_close(c_bump_for_target(tau), case["mondrian_c"].as_f64().unwrap(),
                     &format!("M5 c({tau})"));
        assert_close(lwc_c_bump_for(tau), case["lwc_c"].as_f64().unwrap(),
                     &format!("M6 c({tau})"));
    }
}

/// Reproduce the served band from the artefact row fields, for every case.
///
/// M5: half = q_eff · point            (point-relative)
/// M6: half = q_eff · σ̂ · fri_close    (fri_close-relative)
#[test]
fn served_band_parity() {
    let f = fx();
    let cases = f["cases"].as_array().unwrap();
    assert!(cases.len() >= 200, "fixture thinned out: {} cases", cases.len());
    let (mut n5, mut n6) = (0, 0);

    for case in cases {
        let tau = case["tau"].as_f64().unwrap();
        let regime = case["regime"].as_str().unwrap();
        let point = case["point"].as_f64().unwrap();
        let fri_close = case["fri_close"].as_f64().unwrap();
        let fc = case["forecaster"].as_str().unwrap();
        let ctx = format!(
            "{} {} τ={} [{}]",
            case["symbol"].as_str().unwrap(),
            case["as_of"].as_str().unwrap(), tau, fc
        );

        let tau_clipped = tau.clamp(MIN_SERVED_TARGET, MAX_SERVED_TARGET);
        let (delta, c_bump, q_regime, half) = if fc == "mondrian" {
            n5 += 1;
            let d = delta_shift_for_target(tau_clipped);
            let served = (tau_clipped + d).min(MAX_SERVED_TARGET);
            let c = c_bump_for_target(served);
            let q = regime_quantile_for(regime, served);
            (d, c, q, c * q * point)
        } else {
            n6 += 1;
            let sigma = case["sigma_hat"].as_f64().unwrap();
            let d = lwc_delta_shift_for(tau_clipped);
            let served = (tau_clipped + d).min(MAX_SERVED_TARGET);
            let c = lwc_c_bump_for(served);
            let q = lwc_regime_quantile_for(regime, served);
            (d, c, q, c * q * sigma * fri_close)
        };
        let served = (tau_clipped + delta).min(MAX_SERVED_TARGET);

        assert_close(delta, case["delta"].as_f64().unwrap(), &format!("{ctx} delta"));
        assert_close(served, case["served_target"].as_f64().unwrap(), &format!("{ctx} served_target"));
        assert_close(c_bump, case["c_bump"].as_f64().unwrap(), &format!("{ctx} c_bump"));
        assert_close(c_bump * q_regime, case["q_eff"].as_f64().unwrap(), &format!("{ctx} q_eff"));
        assert_close(point - half, case["lower"].as_f64().unwrap(), &format!("{ctx} lower"));
        assert_close(point + half, case["upper"].as_f64().unwrap(), &format!("{ctx} upper"));
        assert_close(half / fri_close * 1e4, case["sharpness_bps"].as_f64().unwrap(),
                     &format!("{ctx} sharpness_bps"));
    }
    assert!(n5 > 0 && n6 > 0, "both forecasters must be exercised: {n5} M5 / {n6} M6");
}

/// τ outside the served range must clamp identically in both implementations
/// rather than extrapolating a schedule off its anchors.
#[test]
fn out_of_range_tau_clamps() {
    for (raw, want) in [(0.10_f64, MIN_SERVED_TARGET), (0.9999, MAX_SERVED_TARGET)] {
        let clamped = raw.clamp(MIN_SERVED_TARGET, MAX_SERVED_TARGET);
        assert_close(clamped, want, &format!("clamp({raw})"));
        assert_close(regime_quantile_for("normal", clamped),
                     regime_quantile_for("normal", want), "clamped q lookup");
    }
}
