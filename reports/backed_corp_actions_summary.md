# Backed Finance corp-actions — registry-derived summary

Source repos: `backed-fi/cowswap-xstocks-tokenlist`, `backed-fi/backed-tokens-metadata`

Tape contents: **13** commits total across all source repos, **13** classified as corp-action-equivalent events (list / delist / ticker_change / split / dividend / merger / metadata_update / registry_init).

## Commits classified by action type

| action_type     |   n_commits |
|:----------------|------------:|
| list            |           5 |
| metadata_update |           4 |
| delist          |           2 |
| registry_init   |           1 |
| merger          |           1 |

## Commits with extracted xStock tickers

| underlying   | action_type   |   n_commits |
|:-------------|:--------------|------------:|
| AAPLx        | delist        |           1 |
| AZNx         | list          |           1 |
| AZNx         | merger        |           1 |

## Chronological timeline

- **2025-05-30** [`list`] (tickers: —) — [Add testnet bNVDA metadata](https://github.com/backed-fi/backed-tokens-metadata/commit/5c5e1829a79c5b58694d3db8a9b220f85a1cf45c)
- **2026-02-19** [`metadata_update`] (tickers: —) — [update logo](https://github.com/backed-fi/cowswap-xstocks-tokenlist/commit/2a0f784f7df8794b3c4abcd84214aa9f1334b586)
- **2026-02-19** [`delist`] (tickers: —) — [removed Backed references](https://github.com/backed-fi/cowswap-xstocks-tokenlist/commit/5b4928aee5a2724fe6a649430c05584e6319d108)
- **2026-02-19** [`metadata_update`] (tickers: —) — [Update project name in README](https://github.com/backed-fi/cowswap-xstocks-tokenlist/commit/99cd19939af72dc985e661566631f54b9802371a)
- **2026-02-19** [`list`] (tickers: —) — [Add token list](https://github.com/backed-fi/cowswap-xstocks-tokenlist/commit/9dd17e0d5ca3001fe0680982af97c9e752a933dc)
- **2026-02-19** [`list`] (tickers: —) — [Add xStocks Token List to README](https://github.com/backed-fi/cowswap-xstocks-tokenlist/commit/54778c7c3a03ffdc306bce33a83121f78a6149cb)
- **2026-02-19** [`registry_init`] (tickers: —) — [first commit](https://github.com/backed-fi/cowswap-xstocks-tokenlist/commit/a54dc9774a96eec58ca03a0b3d3f6f0b06cb762e)
- **2026-03-03** [`delist`] (tickers: AAPLx, ACNx, BMNRx, BTBTx, BTGOx, COPXx, CRCLx, DFDVx, HDx, HOODx, IWMx, KRAQx, MDTx, NVOx, OPENx, PALLx, PPLTx, SLMTx, SLVx, SPYx, VTx) — [Remove: SLVx, BTGOx, COPXx, DFDVx, OPENx, KRAQx, PALLx, SLMTx, PPLTx, ACNx, HDx, MDTx, BTBTx, IWMx, BMNRx](https://github.com/backed-fi/cowswap-xstocks-tokenlist/commit/3e2626781bd38b218159fc73e241f22643243f12)
- **2026-03-05** [`merger`] (tickers: AZNx, BACx, CMCSAx, CRMx, CRWDx, DHRx, GMEx, GSx, IBMx, IEMGx, LINx, MCDx, MRVLx, NFLXx, ORCLx, STRCx, TBLLx) — [Merge pull request #1 from backed-fi/add-missing-tokens](https://github.com/backed-fi/cowswap-xstocks-tokenlist/commit/496925b8413852ec3d6a3e232d1603919bbac983)
- **2026-03-05** [`list`] (tickers: AZNx, BACx, CMCSAx, CRMx, CRWDx, DHRx, GMEx, GSx, IBMx, IEMGx, LINx, MCDx, MRVLx, NFLXx, ORCLx, STRCx, TBLLx) — [Add TBLLx, ORCLx, STRCx, MCDx, NFLXx, GSx, CMCSAx, BACx, MRVLx, IBMx, CRWDx, IEMGx, LINx, CRMx, DHRx, AZNx, GMEx](https://github.com/backed-fi/cowswap-xstocks-tokenlist/commit/c3e2375eea76f5c3e89b643ceb5bf9cab691702d)
- **2026-03-13** [`metadata_update`] (tickers: —) — [Ran "update" script](https://github.com/backed-fi/cowswap-xstocks-tokenlist/commit/75c49e75e96dcfccf5f8d88e11c54d7f40886e1c)
- **2026-03-13** [`list`] (tickers: —) — [add network analysis](https://github.com/backed-fi/cowswap-xstocks-tokenlist/commit/56c97c58a1f66b3a95d6769e564e3983ac0a3451)
- **2026-03-13** [`metadata_update`] (tickers: —) — [Add update-tokenlist script](https://github.com/backed-fi/cowswap-xstocks-tokenlist/commit/9147d0141baa2dc2181678d376fba4e6f6a3433c)


## Next step

Cross-reference the timeline above against yfinance's `dividends` and `splits` for the matched underlying tickers over the same date range. Each `list` / `delist` / `ticker_change` / `metadata_update` event in this list is a candidate xStock-specific bias entry that yfinance does **not** capture. Re-run the v1b panel build with the merged events and report Δcoverage in §6 / §9 of Paper 1.

On-chain Token-2022 `ScaledUiAmountConfig` cross-validation belongs to OEV grant Month 1 work and is gated on populating `XStock.mint` in `src/soothsayer/universe.py`.
