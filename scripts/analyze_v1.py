"""
V1 analysis: Chainlink weekend bias vs realized Monday-open gap.

Depends on scripts/run_v1_scrape.py having produced
data/processed/v1_chainlink_vs_monday_open.parquet.

Produces:
  - reports/figures/v1_chainlink_bias.png       per-ticker residual plot
  - reports/tables/v1_per_ticker.csv            per-ticker t-stats
  - reports/v1_chainlink_bias.md                human-readable writeup + decision

Run: uv run python scripts/analyze_v1.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from soothsayer.config import DATA_PROCESSED, REPORTS

FIG_DIR = REPORTS / "figures"
TABLE_DIR = REPORTS / "tables"
FIG_DIR.mkdir(parents=True, exist_ok=True)
TABLE_DIR.mkdir(parents=True, exist_ok=True)

# Gate thresholds from H8 plan
POOLED_BIAS_GATE_BP = 10.0    # effect size gate
POOLED_P_GATE = 0.05          # significance gate


def _two_sided_t(mean: float, sd: float, n: int) -> tuple[float, float]:
    if n < 2 or sd == 0 or np.isnan(sd):
        return (np.nan, np.nan)
    t = mean / (sd / np.sqrt(n))
    p = 2 * (1 - stats.t.cdf(abs(t), df=n - 1))
    return (t, p)


def compute_residuals(df: pd.DataFrame) -> pd.DataFrame:
    """Compute g_T, g_hat_CL, e_T, and a duration-normalized residual."""
    df = df.dropna(subset=["fri_close", "mon_open", "cl_mid"]).copy()
    df["g_T"] = np.log(df["mon_open"] / df["fri_close"])
    df["g_hat_cl"] = np.log(df["cl_mid"] / df["fri_close"])
    df["e_T"] = df["g_T"] - df["g_hat_cl"]
    df["e_T_norm"] = df["e_T"] / np.sqrt(df["gap_days"])
    return df


def per_ticker_stats(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for sym, g in df.groupby("symbol"):
        mean = g["e_T"].mean()
        sd = g["e_T"].std(ddof=1)
        t, p = _two_sided_t(mean, sd, len(g))
        rows.append(
            {
                "symbol": sym,
                "n": len(g),
                "mean_bp": mean * 1e4,
                "sd_bp": sd * 1e4,
                "t": t,
                "p": p,
                "ci_half_bp": 1.96 * sd / np.sqrt(len(g)) * 1e4 if len(g) > 1 else np.nan,
            }
        )
    return pd.DataFrame(rows).sort_values("mean_bp").reset_index(drop=True)


def pooled_stats(df: pd.DataFrame) -> dict:
    mean = df["e_T"].mean()
    sd = df["e_T"].std(ddof=1)
    t, p = _two_sided_t(mean, sd, len(df))
    return {"n": len(df), "mean_bp": mean * 1e4, "sd_bp": sd * 1e4, "t": t, "p": p}


def plot_residuals(per_ticker: pd.DataFrame, n_total: int, path: str) -> None:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 4.5))
    y = per_ticker["mean_bp"].to_numpy()
    err = per_ticker["ci_half_bp"].to_numpy()
    ax.errorbar(
        per_ticker["symbol"], y, yerr=err, fmt="o", capsize=4, color="#1f77b4", ecolor="#888"
    )
    ax.axhline(0, color="gray", linestyle="--", alpha=0.5, linewidth=1)
    ax.set_ylabel("Chainlink bias vs realized Monday gap  (bps)")
    ax.set_xlabel("xStock")
    ax.set_title(
        f"V1 — Chainlink weekend bias (per-ticker mean ± 95% CI) — n={n_total} pairs"
    )
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def render_writeup(pooled: dict, per_ticker: pd.DataFrame, df: pd.DataFrame) -> str:
    bias_significant = pooled["p"] < POOLED_P_GATE and abs(pooled["mean_bp"]) > POOLED_BIAS_GATE_BP
    decision = (
        "**GREEN-LIGHT** — Chainlink's weekend aggregation exhibits detectable bias. "
        "Proceed to Phase 1 build."
        if bias_significant
        else "**RETHINK** — Chainlink's weekend bias is not detectable above the 10 bp / 5% gate at this sample size. "
        "Reconsider positioning — possibly pivot to a different axis of improvement (e.g. CI calibration, anomaly/fallback alarms)."
    )

    min_mon = df["weekend_mon"].min()
    max_mon = df["weekend_mon"].max()
    weekend_count = df["weekend_mon"].nunique()

    lines = [
        "# V1 — Chainlink Weekend Bias",
        "",
        "**Hypothesis** ([H8](../docs/hypotheses.md)): the Chainlink Data Streams weekend price (last observation before NYSE open) systematically deviates from the realized Monday-open price.",
        "",
        f"**Sample:** {weekend_count} weekend/long-weekend windows from {min_mon} through {max_mon}, "
        f"8 xStocks (SPYx, QQQx, GOOGLx, AAPLx, NVDAx, TSLAx, MSTRx, HOODx) = **{pooled['n']} (weekend, ticker) pairs**.",
        "",
        "**Method:** for each (weekend, ticker):",
        "- `g_T = ln(P^NYSE_Mon_open / P^NYSE_Fri_close)` — realized Monday gap",
        "- `ĝ_CL = ln(P^CL_Sun-last / P^NYSE_Fri_close)` — Chainlink-implied gap forecast",
        "- `e_T = g_T - ĝ_CL` — residual (positive ⇒ Chainlink underestimated the real move)",
        "",
        "**Gate:** pooled `E[e_T]` significant at 5% **and** |mean| > 10 bp ⇒ green-light Phase 1.",
        "",
        "## Pooled",
        "",
        "| n | mean (bp) | sd (bp) | t | p |",
        "|---|---|---|---|---|",
        f"| {pooled['n']} | {pooled['mean_bp']:+.2f} | {pooled['sd_bp']:.2f} | {pooled['t']:+.2f} | {pooled['p']:.4g} |",
        "",
        "## Per-ticker",
        "",
        per_ticker.round(3).to_markdown(index=False),
        "",
        "## Decision",
        "",
        decision,
        "",
        "![per-ticker residuals](figures/v1_chainlink_bias.png)",
    ]
    return "\n".join(lines)


def main() -> None:
    path = DATA_PROCESSED / "v1_chainlink_vs_monday_open.parquet"
    print(f"loading {path}")
    df_raw = pd.read_parquet(path)
    print(f"rows raw: {len(df_raw)}")

    df = compute_residuals(df_raw)
    print(f"rows with all three prices: {len(df)}")
    print(f"per-symbol coverage: {df.groupby('symbol').size().to_dict()}")

    pooled = pooled_stats(df)
    per = per_ticker_stats(df)

    print("\n=== pooled ===")
    print(
        f"  n={pooled['n']}  mean={pooled['mean_bp']:+.2f}bp  sd={pooled['sd_bp']:.2f}bp  "
        f"t={pooled['t']:+.3f}  p={pooled['p']:.4g}"
    )
    print("\n=== per-ticker ===")
    print(per.to_string(index=False))

    fig_path = FIG_DIR / "v1_chainlink_bias.png"
    plot_residuals(per, pooled["n"], str(fig_path))
    print(f"\nwrote {fig_path}")

    tbl_path = TABLE_DIR / "v1_per_ticker.csv"
    per.to_csv(tbl_path, index=False)
    print(f"wrote {tbl_path}")

    writeup = render_writeup(pooled, per, df)
    report_path = REPORTS / "v1_chainlink_bias.md"
    report_path.write_text(writeup)
    print(f"wrote {report_path}")


if __name__ == "__main__":
    main()
