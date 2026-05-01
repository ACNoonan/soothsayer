# Contributing to soothsayer

Soothsayer is an open-source research project. Contributions are welcome — particularly from people who know statistics, market microstructure, or Solana on-chain data well enough to catch mistakes before they land.

## What kinds of contributions are useful

- **Methodology critique.** If a notebook makes a statistical claim that doesn't hold up, open an issue with the counter-argument and a reference. Replications with different samples are especially valuable.
- **Additional data sources.** New free feeds, better coverage of existing ones, or robust fallbacks when a provider rate-limits us. Add the fetcher and schema in the sibling `scryer` repo first, then consume the resulting parquet from soothsayer via `src/soothsayer/sources/scryer.py` or direct parquet reads.
- **Hypothesis additions.** If you think a signal we haven't considered (say, on-chain congestion, CEX perp basis, options flow) should be tested, open an issue describing the claim, the test, and the gate criterion — same shape as the existing validation tasks.
- **Code quality.** `ruff` catches the obvious stuff; type hints, clearer names, and shorter notebooks help more.

## What we're not looking for (yet)

- New abstractions without concrete users. One notebook or one crate user, please.
- Anchor / on-chain program code — deferred to Week 4 of Phase 1 (see the
  roadmap). The scaffold is Python (Phase 0 validation) and async Rust (Phase 1
  ingest + filter).

## Dev setup

Python (Phase 0 validation):

```bash
uv sync
cp .env.example .env   # fill in HELIUS_API_KEY from dashboard.helius.dev
uv run python -m ipykernel install --user --name soothsayer --display-name "soothsayer"
uv run jupyter lab
```

Rust (Phase 1 build):

```bash
cargo test           # 6 tests today: core types + Chainlink v10 decoder
cargo clippy --all-targets -- -D warnings
```

## Before opening a PR

- `uv run ruff check .` and `uv run ruff format .` pass.
- If you touch a validation notebook, re-run it end-to-end and commit the cleared outputs (strip `cell["outputs"]` and `cell["execution_count"]` — `nbstripout` is fine, a pre-commit hook may be added later).
- Link the relevant hypothesis or issue in the PR description. One logical change per PR.

## Filing issues

- Bugs in code: include the failing command + traceback.
- Methodology disputes: state the claim you're challenging, the data or reference that contradicts it, and the falsifiable implication if you're right.
- New-source proposals: data access pattern (free? keyed? rate limits?), what it replaces or supplements, and which validation benefits.

## License

By contributing, you agree that your contributions will be licensed under Apache-2.0 (see `LICENSE`).
