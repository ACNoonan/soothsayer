# Soothsayer devnet quickstart

> **Status: scaffold — devnet path, commands to be verified end-to-end before partner handoff.**
> Commands below are transcribed from real scripts in the repo (`scripts/deploy_devnet.sh`,
> the `soothsayer-band-amm` CLI, the `soothsayer-publisher` CLI). Steps not yet
> verified as a single clean run are marked `TODO`. This is the companion to
> [`docs/INTEGRATION.md`](INTEGRATION.md). Devnet only — see ROADMAP Phase 3 gates.

Goal: from a clean checkout, deploy the oracle program to devnet, publish one band,
and read it back — in ~15 minutes once the toolchain is installed.

---

## Prerequisites

One-time toolchain (also documented in the header of `scripts/deploy_devnet.sh`):

```bash
# Solana CLI (Anza fork)
sh -c "$(curl -sSfL https://release.anza.xyz/stable/install)"

# Anchor via avm (Anchor.toml pins the workspace; deploy_devnet.sh checks for anchor)
cargo install --git https://github.com/coral-xyz/anchor avm --locked --force
avm install 0.30.1 && avm use 0.30.1
```

TODO: confirm the exact Anchor version the workspace builds against. `deploy_devnet.sh`
does not pin one; `avm use 0.30.1` is the value used in its install notes — verify
against `Anchor.toml [toolchain]` before partner handoff.

RPC endpoint — use a Helius devnet key, never hardcoded:

```bash
export HELIUS_API_KEY=...                      # your devnet key; do NOT commit it
export RPC_URL="https://devnet.helius-rpc.com/?api-key=${HELIUS_API_KEY}"
```

- `scripts/deploy_devnet.sh` selects the cluster with `solana config set --url devnet`
  and does not itself read `RPC_URL`; it airdrops if balance < 2 SOL.
- The `soothsayer-band-amm` CLI reads `RPC_URL` (falls back to public
  `https://api.devnet.solana.com`; `programs/soothsayer-band-amm-cli/src/main.rs`), or
  takes `--rpc <URL>`. Pass the Helius URL there for higher rate limits.

TODO: confirm whether a wallet keypair at `~/.config/solana/id.json` is assumed, or
whether `ANCHOR_WALLET` must be set. `deploy_devnet.sh` defaults to
`~/.config/solana/id.json` and fails if absent.

---

## Step 1 — Deploy the oracle program

```bash
./scripts/deploy_devnet.sh
```

This script (idempotent-ish) checks the toolchain, sets cluster = devnet, tops up the
wallet via airdrop if needed, generates/reuses the program keypair, syncs the program
ID into `declare_id!` + `Anchor.toml`, then runs `anchor build` and
`anchor deploy --provider.cluster devnet`. It prints the deployed program ID.

TODO: verify the script runs clean on a fresh machine (airdrop rate-limits are common
on devnet; the script notes manual top-up is fine).

## Step 2 — Initialize the oracle accounts

`deploy_devnet.sh` prints a sample TS `initialize` call (`PublisherConfig` + `SignerSet`)
but does **not** execute it — the script's own note says a TS integration script
"lands in Week 2.5 (`tests/integration.ts`)".

TODO: supply the actual initialize command. Either (a) the `tests/integration.ts`
runner once it exists, or (b) confirm the `soothsayer-band-amm` CLI's `publish-band`
path performs first-publish against an already-initialized config. Do not invent an
initialize command — verify which one is real before writing it here.

## Step 3 — Publish a band

Two real surfaces exist; pick per track:

**Offline payload (no cluster submit)** — `soothsayer-publisher`:

```bash
cargo run --release -p soothsayer-publisher -- \
  prepare-publish --symbol SPY --as-of 2026-04-17 --target 0.85 --bytes-only
```

Emits the borsh wire bytes for an Anchor `publish` instruction (offline; see the CLI
header in `crates/soothsayer-publisher/src/main.rs`). TODO: document the signing/submit
step that takes these bytes on-chain.

**On-chain devnet publish (AMM track)** — `soothsayer-band-amm` CLI:

```bash
cargo run --release -p soothsayer-band-amm-cli --bin soothsayer-band-amm -- \
  republish-band --symbol SPY --point <P> --lower <L> --upper <U>
```

Writes/updates a `PriceUpdate` PDA via the oracle program (band values passed in
dollars, converted to fixed-point at exp = -8; profile defaults to `2` = amm). Requires
the wallet to match the oracle program's configured `signer_set.root`
(`programs/soothsayer-band-amm-cli/src/main.rs`). TODO: fill the real `<P>/<L>/<U>` from
a `soothsayer-publisher fair-value` read so the published band is a genuine Oracle output.

## Step 4 — Read the band back

```bash
cargo run --release -p soothsayer-band-amm-cli --bin soothsayer-band-amm -- list-available
```

TODO: confirm the exact read/inspect subcommand name and output. Alternatively decode
the PDA directly with `soothsayer-consumer::decode_price_update` (INTEGRATION.md §2).
The consumer crate doc-comment cites a live devnet SPY PDA
(`HfMaU9Qa54fp1V3uh11Qec81RgKUgzT6mxvFkmZ6V3LH`, program
`AgXLLTmUJEVh9EsJnznU1yJaUeE9Ufe7ZotupmDqa7f6`) as a decode target — verify it is still
live before pointing a partner at it.

---

## Optional — full AMM demo pipeline

The `soothsayer-band-amm` CLI has a one-shot `seed-all` subcommand:
`SeedMints → MintToWallet → PublishBand (SPY+QQQ) → InitPool ×2 → Deposit ×2 → Swap ×2`
(`programs/soothsayer-band-amm-cli/src/main.rs`, `Cmd::SeedAll`).

```bash
cargo run --release -p soothsayer-band-amm-cli --bin soothsayer-band-amm -- seed-all --idempotent
```

TODO: verify `seed-all` runs end-to-end against a freshly deployed program and record
the resulting artefact-ledger path
(`research/oracle-conditioned-amm/devnet_artefacts.json` per the CLI default).

---

## Caveats

- Devnet only. Program IDs live in `Anchor.toml [programs.devnet]`; treat them as
  non-permanent.
- On-chain publishes are the M5 path (`forecaster_code = 2`); M6 LWC on-chain enablement
  is pending (INTEGRATION.md §7).
- Never hardcode `HELIUS_API_KEY` — always `${HELIUS_API_KEY}` via env.
