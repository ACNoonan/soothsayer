"""
Dead-simple file cache. Keyed by a logical name + args, backed by parquet for dataframes
and JSON for dicts. Purpose is to avoid burning API quota on re-runs during notebook
iteration — not to be a real caching layer.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from .config import DATA_RAW


def _key(prefix: str, payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str).encode()
    digest = hashlib.sha1(blob).hexdigest()[:12]
    return f"{prefix}_{digest}"


def parquet_cached(
    prefix: str,
    payload: dict[str, Any],
    fetch: Callable[[], pd.DataFrame],
) -> pd.DataFrame:
    path = DATA_RAW / f"{_key(prefix, payload)}.parquet"
    if path.exists():
        return pd.read_parquet(path)
    df = fetch()
    df.to_parquet(path)
    return df


def json_cached(
    prefix: str,
    payload: dict[str, Any],
    fetch: Callable[[], Any],
) -> Any:
    path = DATA_RAW / f"{_key(prefix, payload)}.json"
    if path.exists():
        return json.loads(path.read_text())
    data = fetch()
    path.write_text(json.dumps(data, default=str))
    return data
