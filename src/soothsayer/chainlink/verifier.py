"""
Chainlink Verifier on Solana — two parse paths, one simple & one hard way.

**Easy path: `parse_verify_return_data`.**
The verify instruction calls `set_return_data(&report_data)`, so `meta.returnData`
of any Verifier-touching tx is just the raw bare report bytes (no decompression,
no envelope). Most callers should use this — it's one base64 decode away from a
decoded V10/V11 report.

**Hard path: `parse_verify`.**
Decodes from the raw `verify` instruction data. Keeps the compressed wire format
handling around for cases where the outer program reframes or swallows the
return value.

The instruction-data framing:

  [0..8]    Anchor instruction discriminator
  [8..12]   u32 little-endian — length of signed_report
  [12..]    signed_report (Snappy-compressed)

After snappy decompression, the signed_report is Solidity-ABI encoded as an
outer SignedReport tuple:

  w0..w2    report_context (3 × bytes32, inlined)
  w3        offset to report_data (dynamic bytes)
  ...       signatures follow

At `report_data`: Solidity dynamic-bytes (length word + bytes). The bytes are
the versioned report; first 2 of the embedded feed_id are the schema:

  0x0003 = v3  (crypto / forex)
  0x0007 = v7  (DEX / LP)
  0x0008 = v8  (stables extension)
  0x000a = v10 (24/5 US equities — xStocks, as of Apr 2026)
  0x000b = v11 (v10 + market_status; not yet active on Solana for xStocks)
"""

from __future__ import annotations

import base64
from dataclasses import dataclass

import base58
import snappy

WORD = 32
ANCHOR_DISC_LEN = 8
VEC_LEN_PREFIX = 4


VERIFIER_PROGRAM_ID = "Gt9S41PtjR58CbG9JhJ3J6vxesqrNAswbWYbLNTMZA3c"


@dataclass(frozen=True)
class ParsedVerify:
    raw_report: bytes                 # versioned report bytes (288 v3, 416 v10, 448 v11, ...)
    schema: int                       # first 2 bytes of feed_id
    report_context: bytes | None = None  # 96 bytes; None when parsed from returnData


def parse_verify_return_data(return_data: list | dict | str | None) -> ParsedVerify | None:
    """Extract the decoded report from `meta.returnData` of a Verifier-touching tx.

    Solana JSON-RPC's `returnData` shape: `{'programId': str, 'data': [base64_str, 'base64']}`.
    Helius sometimes returns `[program_id, [base64_str, 'base64']]` list form. Handle both.

    Note on programId: when the Verifier is CPI'd by an outer program (e.g. Kamino's
    Scope oracle `HFn8GnPADiny6XqUoWE8uRPPxb29ikn4yTuPa9MF2fWJ`) and that outer program
    also calls `set_return_data` to forward the Verifier's bytes upward, the
    transaction-level `meta.returnData.programId` ends up as the **outer program**, not
    the Verifier. The payload is byte-identical in either case, so we don't filter on
    programId here; the caller is expected to validate the decoded report (schema,
    feed_id) before trusting it.
    """
    if return_data is None:
        return None
    if isinstance(return_data, dict):
        data_field = return_data.get("data")
    elif isinstance(return_data, list) and len(return_data) == 2:
        _, data_field = return_data
    else:
        return None
    if not data_field:
        return None
    if isinstance(data_field, list) and len(data_field) >= 1:
        raw_b64 = data_field[0]
    elif isinstance(data_field, str):
        raw_b64 = data_field
    else:
        return None
    raw = base64.b64decode(raw_b64)
    if len(raw) < 2:
        return None
    schema = int.from_bytes(raw[:2], "big")
    return ParsedVerify(raw_report=raw, schema=schema, report_context=None)


def _decompress_ix_data(ix_data_base58: str) -> bytes:
    """Strip Anchor disc + Vec<u8> length prefix, then snappy-decompress."""
    raw = base58.b58decode(ix_data_base58)
    if len(raw) < ANCHOR_DISC_LEN + VEC_LEN_PREFIX:
        raise ValueError("instruction data too short for anchor/Vec<u8> framing")
    length = int.from_bytes(
        raw[ANCHOR_DISC_LEN : ANCHOR_DISC_LEN + VEC_LEN_PREFIX], "little"
    )
    payload = raw[ANCHOR_DISC_LEN + VEC_LEN_PREFIX : ANCHOR_DISC_LEN + VEC_LEN_PREFIX + length]
    return snappy.decompress(payload)


def _read_u256(buf: bytes, offset: int) -> int:
    return int.from_bytes(buf[offset : offset + WORD], "big", signed=False)


def parse_verify(ix_data_base58: str) -> ParsedVerify:
    """Parse the full SignedReport envelope from a `verify` instruction's base58-encoded data."""
    decompressed = _decompress_ix_data(ix_data_base58)

    # Head: w0-w2 = reportContext, w3 = offset to reportData
    if len(decompressed) < 4 * WORD:
        raise ValueError(f"decompressed payload too short: {len(decompressed)}")

    report_context = decompressed[0 : 3 * WORD]
    report_data_offset = _read_u256(decompressed, 3 * WORD)

    if report_data_offset + WORD > len(decompressed):
        raise ValueError(f"bad report_data offset {report_data_offset} for payload {len(decompressed)}")

    # At `offset`: u256 length, then that many bytes of report content.
    report_len = _read_u256(decompressed, report_data_offset)
    start = report_data_offset + WORD
    end = start + report_len
    if end > len(decompressed):
        raise ValueError(f"bad report_data extent: {start}..{end} vs payload {len(decompressed)}")
    raw_report = decompressed[start:end]
    if len(raw_report) < 2:
        raise ValueError("raw_report too short to contain feedId prefix")

    schema = int.from_bytes(raw_report[:2], "big")
    return ParsedVerify(
        report_context=report_context, raw_report=raw_report, schema=schema
    )
