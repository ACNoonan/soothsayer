# v1 archive — deprecated scripts (do not run)

These scripts powered the v1 calibration-surface oracle (F1_emp_regime + per-target
buffer schedule + per-(symbol, regime, forecaster, claimed) calibration surface).
They are retained for historical reproduction of the evidence cited in
`reports/v1b_calibration.md`, `reports/v1b_ablation.md`, the early sections of
`reports/paper1_coverage_inversion/`, and `reports/methodology_history.md`
entries dated before the M5 deployment.

**Do not run from this archive.** The v1 calibration-surface APIs
(`compute_calibration_surface`, `pooled_surface`, `invert` in
`src/soothsayer/backtest/calibration.py`) and the v1 Oracle constructor
signature (`Oracle(bounds, surface, surface_pooled, ...)`) were removed in the
M5 refactor. Imports against those names will fail. To resurrect a script
intentionally — e.g., to regenerate a historical table — pin a pre-M5 commit
of `src/soothsayer/oracle.py` and `src/soothsayer/backtest/calibration.py`,
then run from that working tree.

The Mondrian (M5) validation scripts (`run_mondrian_*.py`) are archived here
too: their output tables (`reports/tables/v1b_mondrian_*.csv`) are committed
evidence behind paper 1 §7.7 and the 2026-05-02 methodology_history entry,
and the scripts themselves depended on the v1 calibration-surface API to
serve the deployed Oracle in head-to-head comparisons.

The current deployment artefact is built by
`scripts/build_mondrian_artefact.py`; the demo lives at
`scripts/smoke_oracle.py`.
