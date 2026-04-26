"""JsonlTape — append-only JSONL logger for V5 research tape events.

MVP format is JSONL for ease of inspection during devnet. v1 mainnet
will likely add a Parquet sink alongside JSONL for analysis.

Instrumentation contract: every TapeEvent that the BandEvaluator produces
hits the tape *before* any decision-making logic runs. The tape is the
load-bearing deliverable; the bid logic is secondary.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from soothsayer.bot.types import TapeEvent


class JsonlTape:
    """Append-only JSONL writer for TapeEvents.

    Use as a context manager to ensure flush on close, or call `close()`
    explicitly after use.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("a", encoding="utf-8")

    def append(self, event: TapeEvent) -> None:
        line = json.dumps(event.to_jsonl_dict(), separators=(",", ":"))
        self._fh.write(line)
        self._fh.write("\n")

    def append_many(self, events: Iterable[TapeEvent]) -> None:
        for event in events:
            self.append(event)

    def flush(self) -> None:
        self._fh.flush()

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.flush()
            self._fh.close()

    def __enter__(self) -> "JsonlTape":
        return self

    def __exit__(self, *_args) -> None:
        self.close()
