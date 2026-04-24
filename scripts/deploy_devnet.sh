#!/usr/bin/env bash
#
# Soothsayer devnet deploy + initialize + publish + read-back flow.
#
# Prerequisites (one-time, ~30 min install):
#   # Solana CLI (Anza fork):
#   sh -c "$(curl -sSfL https://release.anza.xyz/stable/install)"
#   # Anchor:
#   cargo install --git https://github.com/coral-xyz/anchor avm --locked --force
#   avm install 0.30.1 && avm use 0.30.1
#
# Once installed, run:
#   ./scripts/deploy_devnet.sh
#
# Environment overrides (all optional):
#   ANCHOR_WALLET=/path/to/keypair.json   (default ~/.config/solana/id.json)
#   PROGRAM_KEYPAIR=/path/to/program-keypair.json   (created if missing)
#   SOL_CLUSTER=devnet|localnet|mainnet   (default devnet)
#
# This script is idempotent-ish: re-running skips steps that are already done.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

ANCHOR_WALLET="${ANCHOR_WALLET:-$HOME/.config/solana/id.json}"
PROGRAM_KEYPAIR="${PROGRAM_KEYPAIR:-$REPO_ROOT/target/deploy/soothsayer_oracle_program-keypair.json}"
SOL_CLUSTER="${SOL_CLUSTER:-devnet}"

say() { printf "\n\033[1;36m▸ %s\033[0m\n" "$*"; }
ok()  { printf "\033[1;32m  ✓ %s\033[0m\n" "$*"; }
fail(){ printf "\033[1;31m  ✗ %s\033[0m\n" "$*" >&2; exit 1; }

say "Checking toolchain"
command -v solana >/dev/null || fail "solana CLI not found — install from https://anza.xyz"
command -v anchor >/dev/null || fail "anchor not found — cargo install --git https://github.com/coral-xyz/anchor avm --locked"
command -v cargo  >/dev/null || fail "cargo not found"
ok "solana $(solana --version | head -1)"
ok "anchor $(anchor --version)"

say "Selecting cluster: $SOL_CLUSTER"
solana config set --url "$SOL_CLUSTER" >/dev/null
ok "cluster set"

say "Checking wallet balance"
[[ -f "$ANCHOR_WALLET" ]] || fail "wallet not found at $ANCHOR_WALLET"
BALANCE_SOL=$(solana balance -k "$ANCHOR_WALLET" | awk '{print $1}')
echo "  balance: $BALANCE_SOL SOL"
if awk -v b="$BALANCE_SOL" 'BEGIN{exit !(b < 2)}'; then
    say "Balance low — requesting airdrop (devnet only)"
    solana airdrop 2 -k "$ANCHOR_WALLET" || echo "  airdrop may be rate-limited; topping up manually is fine"
fi
ok "wallet ready"

if [[ ! -f "$PROGRAM_KEYPAIR" ]]; then
    say "Generating program keypair at $PROGRAM_KEYPAIR"
    mkdir -p "$(dirname "$PROGRAM_KEYPAIR")"
    solana-keygen new --no-bip39-passphrase -o "$PROGRAM_KEYPAIR" -s >/dev/null
fi
PROGRAM_ID=$(solana-keygen pubkey "$PROGRAM_KEYPAIR")
echo "  program id: $PROGRAM_ID"

say "Syncing program ID into source (declare_id! + Anchor.toml)"
sed -i.bak "s/declare_id!(\"[^\"]*\");/declare_id!(\"$PROGRAM_ID\");/" \
    programs/soothsayer-oracle-program/src/lib.rs
sed -i.bak "s/soothsayer_oracle_program = \"[^\"]*\"/soothsayer_oracle_program = \"$PROGRAM_ID\"/" \
    Anchor.toml
rm -f programs/soothsayer-oracle-program/src/lib.rs.bak Anchor.toml.bak
ok "program ID synced"

say "anchor build"
anchor build

say "anchor deploy --provider.cluster $SOL_CLUSTER"
anchor deploy --provider.cluster "$SOL_CLUSTER"

ok "deploy complete — program at $PROGRAM_ID"

say "Initialize accounts (PublisherConfig + SignerSet)"
cat <<EOF
  Next: run the initialize instruction once. Sample TS:

    import * as anchor from "@coral-xyz/anchor";
    const program = anchor.workspace.SoothsayerOracleProgram;
    const authority = anchor.Wallet.payer.publicKey;
    await program.methods.initialize(authority, authority, 30).rpc();

  A TS integration script lands in Week 2.5 (tests/integration.ts).
EOF

say "Deploy flow ready"
echo "  - Program:  $PROGRAM_ID on $SOL_CLUSTER"
echo "  - Wallet:   $ANCHOR_WALLET"
echo "  - To publish a price band:"
echo "      ./target/release/soothsayer prepare-publish --symbol SPY --as-of 2026-04-17 --target 0.95 --bytes-only"
