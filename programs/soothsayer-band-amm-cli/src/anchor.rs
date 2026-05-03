//! Anchor wire-format helpers.
//!
//! Anchor's `#[program]` macro names instructions with the snake-case form of
//! the Rust handler, prefixed by `global:`. The 8-byte discriminator is
//! `sha256(b"global:<name>")[..8]`. Account discriminators use `account:` as
//! the prefix; event discriminators use `event:`. We only need `global:` here.

use sha2::{Digest, Sha256};

/// Compute the 8-byte instruction discriminator for an Anchor IX named
/// `name` (snake_case as it appears in the `#[program]` block).
pub fn ix_discriminator(name: &str) -> [u8; 8] {
    let mut h = Sha256::new();
    h.update(b"global:");
    h.update(name.as_bytes());
    let out = h.finalize();
    let mut d = [0u8; 8];
    d.copy_from_slice(&out[..8]);
    d
}
