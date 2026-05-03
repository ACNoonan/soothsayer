// Soothsayer on-chain program — TS integration test.
// Phase 1 Week 2.5: exercise initialize + publish + read-back against the
// deployed devnet program. Idempotent: re-running on an already-initialized
// program skips initialize and proceeds straight to publish.
//
// Run:
//   ANCHOR_PROVIDER_URL=https://api.devnet.solana.com \
//   ANCHOR_WALLET=$HOME/.config/solana/id.json \
//   npm test

import * as anchor from "@coral-xyz/anchor";
import { BN } from "@coral-xyz/anchor";
import { PublicKey, SystemProgram } from "@solana/web3.js";
import { execSync } from "child_process";
import * as fs from "fs";
import * as path from "path";
import { expect } from "chai";

const IDL_PATH = path.resolve(__dirname, "../target/idl/soothsayer_oracle_program.json");
const PUBLISHER_CLI = path.resolve(__dirname, "../target/release/soothsayer");

// Soothsayer fixed-point exponent default. Matches Python `oracle.py`.
const EXPONENT = -8;

// Anchor's default account-data discriminator length.
const DISC_LEN = 8;

function loadIdl(): anchor.Idl {
  return JSON.parse(fs.readFileSync(IDL_PATH, "utf8"));
}

// Pull a real PricePoint → PublishPayload from the offline publisher CLI.
// Output shape (when bytes_only=false):
//   { payload: { version, regime_code, forecaster_code, exponent,
//                target_coverage_bps, claimed_served_bps, buffer_applied_bps,
//                symbol: "SPY", point, lower, upper, fri_close, fri_ts },
//     bytes_hex: "...", bytes_len: 66, source_pricepoint: {...} }
function preparePayload(symbol: string, asOf: string, target: number) {
  const out = execSync(
    `${PUBLISHER_CLI} prepare-publish --symbol ${symbol} --as-of ${asOf} --target ${target}`,
    { encoding: "utf8" }
  );
  return JSON.parse(out);
}

// Symbol on-wire is `[u8; 16]` ASCII null-padded.
function encodeSymbol(sym: string): number[] {
  const bytes = Buffer.alloc(16);
  Buffer.from(sym, "ascii").copy(bytes);
  return Array.from(bytes);
}

describe("soothsayer-oracle-program (devnet integration)", () => {
  const provider = anchor.AnchorProvider.env();
  anchor.setProvider(provider);

  const idl = loadIdl();
  const programId = new PublicKey(idl.address);
  const program = new anchor.Program(idl, provider);

  const [configPda] = PublicKey.findProgramAddressSync(
    [Buffer.from("config")],
    programId
  );
  const [signerSetPda] = PublicKey.findProgramAddressSync(
    [Buffer.from("signer_set")],
    programId
  );

  before(async () => {
    if (!fs.existsSync(PUBLISHER_CLI)) {
      throw new Error(
        `publisher CLI not built — run \`cargo build --release -p soothsayer-publisher\` first (expected ${PUBLISHER_CLI})`
      );
    }
  });

  it("initialize() — idempotent across reruns", async () => {
    const existing = await provider.connection.getAccountInfo(configPda);
    if (existing) {
      console.log(`  PublisherConfig already exists at ${configPda.toBase58()} — skipping initialize`);
      return;
    }
    const authority = provider.wallet.publicKey;
    const initialSigner = provider.wallet.publicKey;
    const minPublishIntervalSecs = 30;
    const sig = await program.methods
      .initialize(authority, initialSigner, minPublishIntervalSecs)
      .accounts({
        payer: provider.wallet.publicKey,
        config: configPda,
        signerSet: signerSetPda,
        systemProgram: SystemProgram.programId,
      } as any)
      .rpc();
    console.log(`  initialize tx: ${sig}`);

    // Verify state landed on-chain.
    const cfg: any = await (program.account as any).publisherConfig.fetch(configPda);
    expect(cfg.version).to.equal(1);
    expect(cfg.paused).to.equal(0);
    expect(cfg.minPublishIntervalSecs).to.equal(30);
    expect(cfg.authority.toBase58()).to.equal(authority.toBase58());

    const ss: any = await (program.account as any).signerSet.fetch(signerSetPda);
    expect(ss.version).to.equal(1);
    expect(ss.signerCount).to.equal(1);
    expect(Buffer.from(ss.root).equals(initialSigner.toBuffer())).to.equal(true);
  });

  it("publish(SPY) — first symbol; PriceUpdate PDA created in place", async () => {
    const sym = "SPY";
    const asOf = "2026-04-17";
    const target = 0.95;
    const prep = preparePayload(sym, asOf, target);
    console.log(`  source PricePoint: point=${prep.source_pricepoint.point}, lower=${prep.source_pricepoint.lower}, upper=${prep.source_pricepoint.upper}, regime=${prep.source_pricepoint.regime}, forecaster=${prep.source_pricepoint.forecaster_used}`);

    const symBytes = encodeSymbol(sym);
    const [priceUpdatePda] = PublicKey.findProgramAddressSync(
      [Buffer.from("price"), Buffer.from(symBytes)],
      programId
    );

    // Build the on-chain payload from the CLI output. M6_REFACTOR.md A4
    // adds `profileCode` (1=lending default, 2=amm) — the program rejects 0.
    const pl = prep.payload;
    const payload = {
      version: pl.version,
      regimeCode: pl.regime_code,
      forecasterCode: pl.forecaster_code,
      exponent: pl.exponent,
      profileCode: pl.profile_code,
      targetCoverageBps: pl.target_coverage_bps,
      claimedServedBps: pl.claimed_served_bps,
      bufferAppliedBps: pl.buffer_applied_bps,
      symbol: symBytes,
      point: new BN(pl.point),
      lower: new BN(pl.lower),
      upper: new BN(pl.upper),
      friClose: new BN(pl.fri_close),
      friTs: new BN(pl.fri_ts),
    };

    const sig = await program.methods
      .publish(payload as any)
      .accounts({
        signer: provider.wallet.publicKey,
        config: configPda,
        signerSet: signerSetPda,
        priceUpdate: priceUpdatePda,
        systemProgram: SystemProgram.programId,
      } as any)
      .rpc();
    console.log(`  publish tx: ${sig}`);

    // Read back and verify byte-exact storage of the band fields.
    const pu: any = await (program.account as any).priceUpdate.fetch(priceUpdatePda);
    expect(pu.version).to.equal(1);
    expect(pu.exponent).to.equal(EXPONENT);
    expect(pu.targetCoverageBps).to.equal(payload.targetCoverageBps);
    expect(pu.claimedServedBps).to.equal(payload.claimedServedBps);
    expect(pu.bufferAppliedBps).to.equal(payload.bufferAppliedBps);
    expect(pu.regimeCode).to.equal(payload.regimeCode);
    expect(pu.forecasterCode).to.equal(payload.forecasterCode);
    expect(pu.point.toString()).to.equal(payload.point.toString());
    expect(pu.lower.toString()).to.equal(payload.lower.toString());
    expect(pu.upper.toString()).to.equal(payload.upper.toString());
    expect(pu.friTs.toString()).to.equal(payload.friTs.toString());
    expect(Buffer.from(pu.symbol).equals(Buffer.from(symBytes))).to.equal(true);
    expect(pu.signer.toBase58()).to.equal(provider.wallet.publicKey.toBase58());

    // Spot-check on-chain band invariants.
    expect(pu.lower.lte(pu.point)).to.equal(true);
    expect(pu.point.lte(pu.upper)).to.equal(true);

    // Receipt round-trip: decode point/lower/upper to USD and print.
    const scale = Math.pow(10, EXPONENT);
    console.log(
      `  on-chain band: lower=$${(pu.lower.toNumber() * scale).toFixed(2)}, ` +
        `point=$${(pu.point.toNumber() * scale).toFixed(2)}, ` +
        `upper=$${(pu.upper.toNumber() * scale).toFixed(2)} ` +
        `(target=${(pu.targetCoverageBps / 10000).toFixed(2)}, ` +
        `served=${(pu.claimedServedBps / 10000).toFixed(2)})`
    );
  });
});
