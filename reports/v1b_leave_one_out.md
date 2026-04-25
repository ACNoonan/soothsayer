# V1b — Leave-one-symbol-out cross-asset validation

**Question.** The per-symbol coverage results in §6.5 of the paper are computed on a calibration surface that *included* the symbol being scored. A reviewer who picks up the paper and asks *would this work for an unseen ticker?* has no evidence-based answer from §6.5. This diagnostic provides one.

**Method.** For each of the 10 symbols, refit the calibration surface on the *other* nine symbols' pre-2023 data only, then serve the held-out symbol on its 2023+ OOS slice. Because the per-symbol surface for the held-out ticker is empty, the Oracle's surface-inversion code falls through to the pooled (regime-only) surface — the production path for any ticker with sparse history. Compare in-sample realised coverage (full surface) to leave-one-out realised coverage at τ ∈ (0.68, 0.85, 0.95).

## Per-symbol results

| symbol   |   target |   n |   in_sample_realized |   loo_realized |   delta |   in_sample_hw_bps |   loo_hw_bps |   loo_p_uc |   loo_p_ind |
|:---------|---------:|----:|---------------------:|---------------:|--------:|-------------------:|-------------:|-----------:|------------:|
| AAPL     |    0.680 | 172 |                0.674 |          0.674 |   0.000 |             88.819 |       90.421 |      0.875 |       0.109 |
| AAPL     |    0.850 | 172 |                0.826 |          0.820 |  -0.006 |            150.698 |      148.396 |      0.279 |       0.487 |
| AAPL     |    0.950 | 172 |                0.913 |          0.942 |   0.029 |            277.368 |      311.133 |      0.633 |       0.596 |
| GLD      |    0.680 | 172 |                0.686 |          0.715 |   0.029 |             69.930 |       74.738 |      0.318 |       0.123 |
| GLD      |    0.850 | 172 |                0.866 |          0.855 |  -0.012 |            139.120 |      127.802 |      0.864 |       0.682 |
| GLD      |    0.950 | 172 |                0.965 |          0.988 |   0.023 |            215.741 |      223.336 |      0.006 |       0.828 |
| GOOGL    |    0.680 | 172 |                0.593 |          0.657 |   0.064 |             85.472 |       94.335 |      0.520 |       0.492 |
| GOOGL    |    0.850 | 172 |                0.779 |          0.826 |   0.047 |            141.178 |      154.849 |      0.380 |       0.373 |
| GOOGL    |    0.950 | 172 |                0.901 |          0.971 |   0.070 |            249.923 |      296.748 |      0.173 |       0.583 |
| HOOD     |    0.680 | 172 |                0.669 |          0.669 |   0.000 |            183.145 |      183.145 |      0.749 |       0.353 |
| HOOD     |    0.850 | 172 |                0.820 |          0.820 |   0.000 |            308.748 |      308.748 |      0.279 |       0.077 |
| HOOD     |    0.950 | 172 |                0.948 |          0.948 |   0.000 |            598.427 |      598.427 |      0.890 |       0.317 |
| MSTR     |    0.680 | 172 |                0.779 |          0.733 |  -0.047 |            357.217 |      308.566 |      0.133 |       0.462 |
| MSTR     |    0.850 | 172 |                0.953 |          0.924 |  -0.029 |            802.632 |      537.794 |      0.003 |       0.990 |
| MSTR     |    0.950 | 172 |                0.983 |          0.971 |  -0.012 |           1457.815 |      935.278 |      0.173 |       0.117 |
| NVDA     |    0.680 | 172 |                0.698 |          0.674 |  -0.023 |            152.383 |      150.552 |      0.875 |       0.300 |
| NVDA     |    0.850 | 172 |                0.872 |          0.866 |  -0.006 |            263.981 |      252.355 |      0.544 |       0.502 |
| NVDA     |    0.950 | 172 |                0.959 |          0.965 |   0.006 |            527.071 |      583.012 |      0.337 |       0.184 |
| QQQ      |    0.680 | 172 |                0.628 |          0.651 |   0.023 |             67.577 |       68.887 |      0.421 |       0.986 |
| QQQ      |    0.850 | 172 |                0.843 |          0.860 |   0.017 |            108.242 |      110.981 |      0.698 |       0.090 |
| QQQ      |    0.950 | 172 |                0.948 |          0.953 |   0.006 |            196.482 |      206.751 |      0.832 |       0.375 |
| SPY      |    0.680 | 172 |                0.587 |          0.599 |   0.012 |             49.703 |       50.718 |      0.025 |       0.082 |
| SPY      |    0.850 | 172 |                0.802 |          0.802 |   0.000 |             82.954 |       82.293 |      0.092 |       0.164 |
| SPY      |    0.950 | 172 |                0.930 |          0.965 |   0.035 |            144.604 |      157.114 |      0.337 |       0.509 |
| TLT      |    0.680 | 172 |                0.750 |          0.738 |  -0.012 |             80.435 |       79.000 |      0.095 |       0.108 |
| TLT      |    0.850 | 172 |                0.884 |          0.860 |  -0.023 |            123.340 |      122.094 |      0.698 |       0.695 |
| TLT      |    0.950 | 172 |                0.988 |          0.988 |   0.000 |            207.091 |      212.241 |      0.006 |       0.828 |
| TSLA     |    0.680 | 172 |                0.721 |          0.703 |  -0.017 |            224.496 |      219.098 |      0.506 |       0.690 |
| TSLA     |    0.850 | 172 |                0.907 |          0.884 |  -0.023 |            389.904 |      339.444 |      0.200 |       0.213 |
| TSLA     |    0.950 | 172 |                0.965 |          0.977 |   0.012 |            685.695 |      725.986 |      0.073 |       0.662 |

## Pooled across held-out symbols

| split         |   target |   n_total |   weighted_realized |   weighted_hw_bps |
|:--------------|---------:|----------:|--------------------:|------------------:|
| in_sample     |    0.680 |      1720 |               0.678 |           135.918 |
| in_sample     |    0.850 |      1720 |               0.855 |           251.080 |
| in_sample     |    0.950 |      1720 |               0.950 |           456.022 |
| leave_one_out |    0.680 |      1720 |               0.681 |           131.946 |
| leave_one_out |    0.850 |      1720 |               0.852 |           218.476 |
| leave_one_out |    0.950 |      1720 |               0.967 |           425.003 |

## Reading

**If LOO realised tracks in-sample within ~2pp at τ=0.85 and τ=0.95:** the calibration *mechanism* transfers to unseen tickers — the per-symbol surface contributes refinement, but the regime-pooled fallback delivers the headline calibration claim by itself. This supports a paper claim that the methodology generalises to tickers outside our 10-symbol universe (subject to the same regime-labeler and factor-switchboard).

**If specific symbols show large LOO drops:** those tickers' per-symbol surfaces were doing real work, and the methodology requires symbol-specific calibration to deliver the headline number. This narrows the generalisation claim from "the mechanism" to "the mechanism + per-symbol fitted surface". Disclose accordingly.

Raw artefacts: `reports/tables/v1b_leave_one_out.csv`. Reproducible via `scripts/run_leave_one_out.py`.