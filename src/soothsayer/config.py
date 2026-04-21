from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = REPO_ROOT / "data" / "raw"
DATA_PROCESSED = REPO_ROOT / "data" / "processed"
REPORTS = REPO_ROOT / "reports"

for _p in (DATA_RAW, DATA_PROCESSED, REPORTS):
    _p.mkdir(parents=True, exist_ok=True)

load_dotenv(REPO_ROOT / ".env", override=False)

HELIUS_API_KEY = os.environ.get("HELIUS_API_KEY", "")
SOLANA_RPC_URL = os.environ.get("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")


def helius_rpc_url() -> str:
    if not HELIUS_API_KEY:
        raise RuntimeError("HELIUS_API_KEY not set in .env")
    return f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"


def helius_enhanced_tx_base() -> str:
    if not HELIUS_API_KEY:
        raise RuntimeError("HELIUS_API_KEY not set in .env")
    return f"https://api.helius.xyz/v0"
