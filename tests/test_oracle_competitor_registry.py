from __future__ import annotations

import unittest
from pathlib import Path

import pyarrow.parquet as pq

from soothsayer.config import SCRYER_DATASET_ROOT

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = (
    WORKSPACE_ROOT / "docs" / "sources" / "oracles" / "competitor_oracle_registry.md"
)
ORACLE_DOCS = {
    "chainlink_v10": WORKSPACE_ROOT / "docs" / "sources" / "oracles" / "chainlink_v10.md",
    "chainlink_v11": WORKSPACE_ROOT / "docs" / "sources" / "oracles" / "chainlink_v11.md",
    "pyth_regular": WORKSPACE_ROOT / "docs" / "sources" / "oracles" / "pyth_regular.md",
    "pyth_lazer": WORKSPACE_ROOT / "docs" / "sources" / "oracles" / "pyth_lazer.md",
    "redstone_live": WORKSPACE_ROOT / "docs" / "sources" / "oracles" / "redstone_live.md",
}
INDEX_PATH = WORKSPACE_ROOT / "docs" / "sources" / "INDEX.md"


def _first_parquet_file(root: Path) -> Path | None:
    if not root.exists():
        return None
    for path in root.rglob("*.parquet"):
        return path
    return None


def _parquet_columns(path: Path) -> set[str]:
    return set(pq.ParquetFile(path).schema.names)


class OracleCompetitorRegistryTests(unittest.TestCase):
    def test_registry_has_current_canonical_urls(self) -> None:
        text = REGISTRY_PATH.read_text()
        required_urls = [
            "https://docs.chain.link/data-streams/reference/report-schema-v10",
            "https://docs.chain.link/data-streams/reference/report-schema-v11",
            "https://docs.pyth.network/price-feeds/pro/payload-reference",
            "https://docs.pyth.network/price-feeds/core/market-hours",
            "https://docs.redstone.finance/docs/dapps/redstone-live-feeds/",
        ]
        for url in required_urls:
            self.assertIn(url, text)

    def test_registry_has_non_regression_rules(self) -> None:
        text = REGISTRY_PATH.read_text()
        self.assertIn("Hard anti-regression rules", text)
        self.assertIn("Do not collapse Chainlink v10 and v11", text)
        self.assertIn("Do not describe Pyth `conf` as a calibrated coverage guarantee", text)
        self.assertIn("Do not claim RedStone publishes a confidence interval", text)

    def test_oracle_docs_link_back_to_registry(self) -> None:
        for name, path in ORACLE_DOCS.items():
            with self.subTest(name=name):
                text = path.read_text()
                self.assertIn("Canonical registry row:", text)
                self.assertIn("competitor_oracle_registry.md", text)

    def test_sources_index_lists_registry_first(self) -> None:
        text = INDEX_PATH.read_text()
        self.assertIn("oracles/competitor_oracle_registry.md", text)
        self.assertIn("Canonical comparator contract", text)

    def test_local_scryer_schema_audit_if_present(self) -> None:
        surfaces = [
            (
                SCRYER_DATASET_ROOT / "pyth" / "oracle_tape" / "v1",
                {"pyth_price", "pyth_conf", "pyth_publish_time", "_schema_version"},
            ),
            (
                SCRYER_DATASET_ROOT / "redstone" / "oracle_tape" / "v1",
                {"value", "redstone_ts", "provider_pubkey", "_schema_version"},
            ),
            (
                SCRYER_DATASET_ROOT / "soothsayer_v5" / "tape" / "v1",
                {"cl_tokenized_px", "cl_venue_px", "cl_market_status", "_schema_version"},
            ),
            (
                SCRYER_DATASET_ROOT / "chainlink_data_streams" / "report_tape" / "v1",
                {"_schema_version"},
            ),
        ]

        any_surface_found = False
        for root, required_cols in surfaces:
            parquet_path = _first_parquet_file(root)
            if parquet_path is None:
                continue
            any_surface_found = True
            cols = _parquet_columns(parquet_path)
            missing = required_cols - cols
            self.assertFalse(
                missing,
                msg=f"Missing columns {sorted(missing)} in {parquet_path}",
            )

        if not any_surface_found:
            self.skipTest("No local scryer parquet surfaces found for optional schema audit.")


if __name__ == "__main__":
    unittest.main()
