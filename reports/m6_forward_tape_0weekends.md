# M6 LWC forward-tape — 0 weekends since freeze

**Generated:** 2026-05-04 22:16 UTC.

No forward weekends with complete coverage have landed in the scryer parquet since the M6 LWC artefact was frozen. The harness fires on its launchd cadence (Tuesday 09:30 local time) and will populate this report once at least one complete forward weekend is available.

Most likely cause of an empty tape: at least one of the four scryer runners (`equities-daily`, `earnings`, `cme-intraday-1m`, `cboe-indices`) had a recent failure or gap that left a Friday or Monday bar missing for the panel's exogenous factors. The wrapper script's SLA pre-check (`scripts/check_scryer_freshness.py`) flags any runner that's missed its 26h SLA; check `~/Library/Logs/soothsayer-forward-tape.log` for the most recent fire's summary.
