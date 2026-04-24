"""
Calibration backtest for the Soothsayer fair-value methodology.

Validates, on a decade of underlying-equity weekends, that a fair-value forecast
published at Friday 16:00 ET produces calibrated confidence intervals against
the Monday 09:30 open. The xStock-specific test comes later; this module
answers whether the methodology itself holds water before any xStock parameter
estimation.

Forecasters:
  F0  Stale hold (Chainlink analog)
  F1  Naive futures-adjusted (ES/NQ weekend return applied to Friday close)
  F2  Futures + HAR-RV conditional vol scaling
  F3  Full FV stack (VECM + Madhavan-Sobczyk + regime multiplier) — deferred
"""
