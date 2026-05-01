from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = REPO_ROOT / "data" / "raw"
DATA_PROCESSED = REPO_ROOT / "data" / "processed"
REPORTS = REPO_ROOT / "reports"

load_dotenv(REPO_ROOT / ".env", override=False)

# Canonical scryer dataset root. scryer's launchd-managed live tapes write to
# Application Support, not ~/Documents/, due to macOS 26.x TCC restrictions
# on launchd reading user-document directories. Override with the
# SCRYER_DATASET_ROOT env var for testing against a different scryer
# checkout (e.g., the sibling-repo `../scryer/dataset` for offline replays).
SCRYER_DATASET_ROOT = Path(
    os.environ.get(
        "SCRYER_DATASET_ROOT",
        str(Path.home() / "Library" / "Application Support" / "scryer" / "dataset"),
    )
)

for _p in (DATA_RAW, DATA_PROCESSED, REPORTS):
    _p.mkdir(parents=True, exist_ok=True)

HELIUS_API_KEY = os.environ.get("HELIUS_API_KEY", "")
SOLANA_RPC_URL = os.environ.get("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")

RPCFAST_API_KEY = os.environ.get("RPCFAST_API_KEY", "")
RPCFAST_RPC_URL_BASE = os.environ.get("RPCFAST_RPC_URL", "https://solana-rpc.rpcfast.com")

# Default provider for standard Solana JSON-RPC — "helius" (faster single-call latency)
# or "rpcfast" (larger rate budget: 15 req/s + 1.5M CU/mo). Enhanced Transactions API
# (V4 DEX swap extraction) always hits Helius regardless.
PRIMARY_RPC = os.environ.get("PRIMARY_RPC", "helius").lower()


def helius_rpc_url() -> str:
    if not HELIUS_API_KEY:
        raise RuntimeError("HELIUS_API_KEY not set in .env")
    return f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"


def helius_enhanced_tx_base() -> str:
    if not HELIUS_API_KEY:
        raise RuntimeError("HELIUS_API_KEY not set in .env")
    return f"https://api.helius.xyz/v0"


def rpcfast_rpc_url() -> str:
    if not RPCFAST_API_KEY:
        raise RuntimeError("RPCFAST_API_KEY not set in .env")
    return f"{RPCFAST_RPC_URL_BASE}/?api_key={RPCFAST_API_KEY}"
