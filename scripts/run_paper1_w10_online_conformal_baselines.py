"""
W10 — online-conformal baselines: ACI, DtACI, and conformal PI.

Why this exists
---------------
§7's comparator set (constant buffer, unweighted Mondrian, GARCH-t,
GARCH-Gaussian) contains no *adaptive conformal* method. Schmitt's
regime-weighted conformal calibration (arXiv:2602.03903, q-fin.RM)
benchmarks against exactly ACI / DtACI / conformal PID, which makes that
trio the convention in the conformal-VaR literature. A referee who knows
that literature asks for it first. This runner supplies it.

  ACI    Gibbs & Candès 2021, arXiv:2106.00170
  DtACI  Gibbs & Candès 2022, arXiv:2208.08401
  PI     Angelopoulos, Candès & Tibshirani 2023, arXiv:2307.16895

Fairness commitments (each one exists to forestall a "you crippled the
baseline" objection):

  1. Same panel, same point estimator, same 2023-01-01 split, same metrics
     as every other §7 comparator.
  2. Online state is **warmed up on the training period** so the baselines
     see exactly the data the split-conformal arms are fit on. Only
     2023+ rows are scored.
  3. Run in **both** score spaces: the unstandardised relative residual
     (`raw`, the honest like-for-like against an architecture-free
     baseline) and the σ̂-standardised score (`lwc` — this *hands the
     baseline our per-symbol fix* and asks whether ACI could then replace
     the Mondrian quantile).
  4. Run **per-symbol** as well as pooled. Pooled ACI has no per-symbol
     channel; per-symbol ACI does, and is the strong form of the baseline.
  5. ACI is reported at a default γ *and* at its oracle-best γ chosen on
     the evaluation slice — a configuration we could not deploy, granted
     to the baseline anyway.

Definitions
-----------
point      = fri_close · (1 + factor_ret)                (§7.4 switchboard)
score_raw  = |mon_open − point| / fri_close
score_lwc  = score_raw / σ̂_sym_pre_fri
band       = point ∓ q · fri_close             (raw)
             point ∓ q · σ̂ · fri_close         (lwc)

so `q` is a radius in score units and the online methods differ only in
how q_t is chosen at each weekend.

Outputs
-------
  reports/tables/w10_online_conformal_baselines.csv   full grid
  reports/tables/w10_online_conformal_headline.csv    τ=0.95 headline

Run
---
  ./.venv/bin/python scripts/run_paper1_w10_online_conformal_baselines.py
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from soothsayer.backtest import metrics as met
from soothsayer.backtest.calibration import (
    DEFAULT_TAUS,
    fit_split_conformal_forecaster,
    prep_panel_for_forecaster,
    serve_bands_forecaster,
)
from soothsayer.config import DATA_PROCESSED, REPORTS

SPLIT_DATE = date(2023, 1, 1)
# The overnight panel's σ̂ MUST exclude earnings residuals from the scale pool
# (build_overnight_panel.py builds it that way). prep_panel_for_forecaster
# recomputes σ̂, so omitting this silently substitutes a contaminated scale:
# +32% σ̂ on GOOGL, +23% on NVDA, over-widening every ordinary night.
SIGMA_EXCL = {"weekend": None, "overnight": "earnings_next_week"}
ACI_GAMMA_DEFAULT = 0.01
ACI_GAMMA_GRID = (0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1)
# DtACI expert bank + aggregation constants. η/σ follow the paper's
# local-adaptation heuristic with a lookback of I weekends; they are stated
# here rather than tuned, and the γ grid is the same one swept for ACI.
DTACI_I = 100


# ----------------------------------------------------------------- helpers
def _empirical_radius(past: np.ndarray, alpha: float) -> float:
    """Radius = the (1-alpha) empirical quantile of past scores.

    alpha <= 0 → an interval that covers everything; alpha >= 1 → a
    degenerate zero-width interval. Both are legitimate ACI states and are
    what makes it able to recover from a coverage debt."""
    if alpha <= 0.0:
        return np.inf
    if alpha >= 1.0:
        return 0.0
    if past.size == 0:
        return np.inf
    return float(np.quantile(past, 1.0 - alpha))


def _run_aci(weekend_scores: list[np.ndarray], alpha_target: float,
             gamma: float, n_warm: int) -> list[np.ndarray]:
    """ACI. Returns the served radius for each row of each weekend.

    α_{t+1} = α_t + γ(α − err_t), err_t = realised miscoverage at t.
    With a panel, err_t is the *fraction* of that weekend's symbols outside
    the band — the natural multi-series reading of the {0,1} indicator, and
    lower-variance than collapsing the weekend to a single Bernoulli draw.
    """
    alpha_t = alpha_target
    past: list[np.ndarray] = []
    out: list[np.ndarray] = []
    for t, s in enumerate(weekend_scores):
        flat = np.concatenate(past) if past else np.array([])
        q = _empirical_radius(flat, alpha_t)
        if t >= n_warm:
            out.append(np.full(s.shape, q))
        err = float(np.mean(s > q)) if s.size else 0.0
        alpha_t = float(np.clip(alpha_t + gamma * (alpha_target - err), -1.0, 2.0))
        past.append(s)
    return out


def _run_dtaci(weekend_scores: list[np.ndarray], alpha_target: float,
               n_warm: int) -> list[np.ndarray]:
    """DtACI: a bank of ACI experts with different γ, exponentially weighted.

    Each expert i keeps its own α^i and updates it by the ACI rule. Weights
    move on the pinball loss of each expert's served radius, then are mixed
    toward uniform so a stale expert can recover. The served α is the
    weight-average of the experts' α — this removes ACI's γ-selection, which
    is the entire point of the method.
    """
    gammas = np.array(ACI_GAMMA_GRID, dtype=float)
    k = gammas.size
    alphas = np.full(k, alpha_target, dtype=float)
    w = np.ones(k) / k
    eta = float(np.sqrt(3.0 / DTACI_I * (np.log(k * DTACI_I) + 2.0)))
    sigma = 1.0 / (2.0 * DTACI_I)

    past: list[np.ndarray] = []
    out: list[np.ndarray] = []
    for t, s in enumerate(weekend_scores):
        flat = np.concatenate(past) if past else np.array([])
        q_i = np.array([_empirical_radius(flat, a) for a in alphas])
        alpha_bar = float(np.dot(w, alphas))
        q_bar = _empirical_radius(flat, alpha_bar)
        if t >= n_warm:
            out.append(np.full(s.shape, q_bar))

        if s.size:
            # Pinball loss at level (1-α) for each expert, averaged over the
            # weekend's symbols; finite radii only (an infinite radius is
            # trivially covering and would otherwise dominate the weights).
            losses = np.zeros(k)
            for i in range(k):
                if not np.isfinite(q_i[i]):
                    losses[i] = np.max(s) * alpha_target
                    continue
                d = s - q_i[i]
                losses[i] = float(np.mean(
                    np.where(d > 0, alpha_target * d, (alpha_target - 1.0) * d)
                ))
            w = w * np.exp(-eta * losses)
            tot = w.sum()
            w = np.ones(k) / k if (tot <= 0 or not np.isfinite(tot)) else w / tot
            w = (1.0 - sigma) * w + sigma / k

            for i in range(k):
                err_i = float(np.mean(s > q_i[i]))
                alphas[i] = float(np.clip(
                    alphas[i] + gammas[i] * (alpha_target - err_i), -1.0, 2.0
                ))
        past.append(s)
    return out


def _run_pi(weekend_scores: list[np.ndarray], alpha_target: float,
            n_warm: int, lr: float | None = None) -> list[np.ndarray]:
    """Conformal PI — quantile tracker (P) plus integrator (I).

    q_{t+1} = q_t + η(err_t − α) + r_t(Σ_{s≤t}(err_s − α))

    This is conformal PID *without the scorecaster* (the D/forecast term).
    A scorecaster would require choosing and fitting a score-forecasting
    model, which is a design decision we would then have to defend as part
    of the baseline; the P+I form is the standard model-free configuration.
    Labelled `pi` throughout, never `pid`, so the table does not overclaim.

    η defaults to a scale tied to the training-score spread, since q lives
    in score units and a fixed step would be meaningless across the raw and
    σ̂-standardised score spaces.
    """
    warm = np.concatenate(weekend_scores[:n_warm]) if n_warm else np.array([])
    if lr is None:
        lr = float(np.quantile(warm, 0.95) * 0.05) if warm.size else 0.01
    q = float(np.quantile(warm, 1.0 - alpha_target)) if warm.size else 0.0
    integral = 0.0
    c_sat = 5.0
    k_i = lr
    out: list[np.ndarray] = []
    for t, s in enumerate(weekend_scores):
        if t >= n_warm:
            out.append(np.full(s.shape, max(q, 0.0)))
        if s.size:
            err = float(np.mean(s > q))
            integral += err - alpha_target
            # Saturating integral term (Angelopoulos et al. §2.2): grows
            # sub-linearly so a long coverage debt cannot blow the band up.
            tt = max(t + 1, 2)
            r = k_i * np.tan(np.clip(
                integral * np.log(tt) / (tt * c_sat), -1.5, 1.5
            ))
            q = q + lr * (err - alpha_target) + r
        else:
            out.append(np.array([]))
    return out


# ------------------------------------------------------------- band + score
def _serve(method: str, work: pd.DataFrame, score_col: str, scale: np.ndarray,
           tau: float, grouping: str) -> pd.Series:
    """Return the served radius per row (index-aligned to `work`)."""
    alpha = 1.0 - tau
    radius = pd.Series(np.nan, index=work.index, dtype=float)

    def _drive(sub: pd.DataFrame) -> None:
        wk = sub.groupby("fri_ts", sort=True)
        keys = list(wk.groups.keys())
        seqs = [sub.loc[wk.groups[k], score_col].to_numpy(float) for k in keys]
        n_warm = sum(1 for k in keys if k < SPLIT_DATE)
        if method == "aci":
            served = _run_aci(seqs, alpha, ACI_GAMMA_DEFAULT, n_warm)
        elif method.startswith("aci_g"):
            served = _run_aci(seqs, alpha, float(method.split("aci_g")[1]), n_warm)
        elif method == "dtaci":
            served = _run_dtaci(seqs, alpha, n_warm)
        elif method == "pi":
            served = _run_pi(seqs, alpha, n_warm)
        else:
            raise ValueError(method)
        for k, vals in zip(keys[n_warm:], served):
            radius.loc[wk.groups[k]] = vals

    if grouping == "pooled":
        _drive(work)
    else:
        for _, sub in work.groupby("symbol", sort=True):
            _drive(sub)
    return radius


def _metrics(oos: pd.DataFrame, lower: pd.Series, upper: pd.Series,
             tau: float, label: dict) -> dict:
    band = pd.DataFrame({"lower": lower, "upper": upper})
    m = oos["mon_open"].notna() & band["lower"].notna() & band["upper"].notna()
    p, b = oos.loc[m], band.loc[m]
    inside = (p["mon_open"] >= b["lower"]) & (p["mon_open"] <= b["upper"])
    v = (~inside).astype(int).to_numpy()
    lr_uc, p_uc = met._lr_kupiec(v, tau)
    cc = met.conditional_coverage_from_bounds(p, {tau: b}, group_by="symbol").iloc[0]

    # Per-symbol Kupiec pass count — the claim §7.2 turns on.
    npass, ntot = 0, 0
    for sym, sub in p.groupby("symbol"):
        sb = b.loc[sub.index]
        ins = (sub["mon_open"] >= sb["lower"]) & (sub["mon_open"] <= sb["upper"])
        _, ps = met._lr_kupiec((~ins).astype(int).to_numpy(), tau)
        ntot += 1
        npass += int(np.isfinite(ps) and ps >= 0.05)

    # Per-REGIME Kupiec. W12 (2026-07-24) showed this is the axis a pooled
    # quantile fails on even when it passes per-symbol — catastrophically so
    # on earnings_night. Measuring only per-symbol is what made the first
    # reading of this grid wrong.
    rpass, rtot, rdetail = 0, 0, {}
    for reg, sub in p.groupby("regime_pub"):
        sb = b.loc[sub.index]
        ins = (sub["mon_open"] >= sb["lower"]) & (sub["mon_open"] <= sb["upper"])
        _, pr = met._lr_kupiec((~ins).astype(int).to_numpy(), tau)
        rtot += 1
        rpass += int(np.isfinite(pr) and pr >= 0.05)
        rdetail[f"realised_{reg}"] = float(ins.mean())

    hw = ((b["upper"] - b["lower"]) / 2 / p["fri_close"] * 1e4)
    return {
        **label, "tau": tau, "n": int(m.sum()),
        "realised": float(inside.mean()),
        "half_width_bps": float(hw.replace([np.inf, -np.inf], np.nan).mean()),
        "kupiec_p": float(p_uc),
        "christ_p": float(cc["p_ind"]),
        "per_symbol_kupiec_pass": npass,
        "per_symbol_n": ntot,
        "per_regime_kupiec_pass": rpass,
        "per_regime_n": rtot,
        **rdetail,
    }


PANELS = [("weekend", "v1b_panel"), ("overnight", "overnight_panel")]


def run_panel(panel_name: str, fname: str, rows: list) -> None:
    panel = pd.read_parquet(DATA_PROCESSED / f"{fname}.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(
        subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]
    ).reset_index(drop=True)
    panel["regime_pub"] = panel["regime_pub"].astype(str)

    work = prep_panel_for_forecaster(
        panel, "lwc", sigma_exclude_mask_col=SIGMA_EXCL[panel_name]).copy()
    work["point"] = work["fri_close"] * (1.0 + work["factor_ret"])
    work["score_lwc"] = work["score"]
    work["score_raw"] = (work["mon_open"] - work["point"]).abs() / work["fri_close"]
    work = work.dropna(
        subset=["score_lwc", "score_raw", "sigma_hat_sym_pre_fri"]
    ).sort_values(["fri_ts", "symbol"]).reset_index(drop=True)

    n_oos = int((work["fri_ts"] >= SPLIT_DATE).sum())
    print(f"panel: {len(work):,} rows · {work['fri_ts'].nunique()} weekends · "
          f"{work['symbol'].nunique()} symbols · OOS rows {n_oos:,}", flush=True)

    # ---- deployed reference (identical split / metrics) -------------------
    dep_panel = prep_panel_for_forecaster(
        panel, "lwc", sigma_exclude_mask_col=SIGMA_EXCL[panel_name])
    qt, cb, _ = fit_split_conformal_forecaster(
        dep_panel, SPLIT_DATE, "lwc", cell_col="regime_pub")
    dep_oos = (dep_panel[dep_panel["fri_ts"] >= SPLIT_DATE]
               .dropna(subset=["score"]).sort_values(["fri_ts", "symbol"])
               .reset_index(drop=True))
    dep_bounds = serve_bands_forecaster(
        dep_oos, qt, cb, "lwc", cell_col="regime_pub", taus=DEFAULT_TAUS)
    for tau in DEFAULT_TAUS:
        rows.append(_metrics(
            dep_oos, dep_bounds[tau]["lower"], dep_bounds[tau]["upper"], tau,
            {"panel": panel_name, "method": "deployed_lwc_mondrian",
             "grouping": "per_regime", "score_space": "lwc"}))
    print("deployed reference scored", flush=True)

    # ---- online baselines -------------------------------------------------
    oos_mask = work["fri_ts"] >= SPLIT_DATE
    for space in ("raw", "lwc"):
        score_col = f"score_{space}"
        scale = (work["sigma_hat_sym_pre_fri"].to_numpy(float)
                 if space == "lwc" else np.ones(len(work)))
        for method in ("aci", "dtaci", "pi"):
            for grouping in ("pooled", "per_symbol"):
                for tau in DEFAULT_TAUS:
                    rad = _serve(method, work, score_col, scale, tau, grouping)
                    hw = rad.to_numpy(float) * scale * work["fri_close"].to_numpy(float)
                    lo = pd.Series(work["point"].to_numpy(float) - hw, index=work.index)
                    up = pd.Series(work["point"].to_numpy(float) + hw, index=work.index)
                    rows.append(_metrics(
                        work[oos_mask], lo[oos_mask], up[oos_mask], tau,
                        {"panel": panel_name, "method": method,
                         "grouping": grouping, "score_space": space}))
                print(f"  {space}/{method}/{grouping} done", flush=True)

    # ---- ACI oracle-best γ (chosen ON the evaluation slice) ---------------
    # Weekend only: 7x the cost, and it is a fairness bonus rather than a
    # headline arm. Overnight conclusions rest on the default-γ arms.
    for space in (("raw", "lwc") if panel_name == "weekend" else ()):
        score_col = f"score_{space}"
        scale = (work["sigma_hat_sym_pre_fri"].to_numpy(float)
                 if space == "lwc" else np.ones(len(work)))
        for grouping in ("pooled", "per_symbol"):
            for tau in DEFAULT_TAUS:
                best = None
                for g in ACI_GAMMA_GRID:
                    rad = _serve(f"aci_g{g}", work, score_col, scale, tau, grouping)
                    hw = rad.to_numpy(float) * scale * work["fri_close"].to_numpy(float)
                    lo = pd.Series(work["point"].to_numpy(float) - hw, index=work.index)
                    up = pd.Series(work["point"].to_numpy(float) + hw, index=work.index)
                    r = _metrics(work[oos_mask], lo[oos_mask], up[oos_mask], tau,
                                 {"panel": panel_name, "method": "aci_oracle_gamma",
                                  "grouping": grouping, "score_space": space})
                    r["gamma"] = g
                    # "best" = most per-symbol Kupiec passes, then closest to nominal
                    keyr = (r["per_symbol_kupiec_pass"],
                            -abs(r["realised"] - tau))
                    if best is None or keyr > best[0]:
                        best = (keyr, r)
                rows.append(best[1])
            print(f"  {space}/aci_oracle_gamma/{grouping} done", flush=True)


def main() -> None:
    rows: list = []
    for panel_name, fname in PANELS:
        print(f"\n########## PANEL: {panel_name} ##########", flush=True)
        run_panel(panel_name, fname, rows)

    out = pd.DataFrame(rows)
    tdir = REPORTS / "tables"
    tdir.mkdir(parents=True, exist_ok=True)
    out.to_csv(tdir / "w10_online_conformal_baselines.csv", index=False)

    head = out[out["tau"] == 0.95].sort_values(
        ["per_symbol_kupiec_pass", "kupiec_p"], ascending=False)
    head.to_csv(tdir / "w10_online_conformal_headline.csv", index=False)

    print("\n" + "=" * 104)
    print("τ = 0.95 — OOS 2023+   (per-symbol Kupiec pass is the §7.2 claim)")
    print("=" * 104)
    print(head[["method", "grouping", "score_space", "n", "realised",
                "half_width_bps", "kupiec_p", "christ_p",
                "per_symbol_kupiec_pass", "per_symbol_n"]]
          .to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print(f"\nWrote {tdir / 'w10_online_conformal_baselines.csv'}")


if __name__ == "__main__":
    main()
