"""Content-addressed caches for Jev decisions.

The corpus is frozen, so an identical (model, state, questions) call always
returns an equivalent answer — caching makes reruns free and reproducible.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Protocol

from ipl_sentiment_trading.jev.types import DecideResult, Question


def cache_key(model: str, state: str, questions: dict[str, Question]) -> str:
    payload = {
        "model": model,
        "state": state,
        "questions": {k: q.model_dump() for k, q in sorted(questions.items())},
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class Cache(Protocol):
    def get(self, key: str) -> DecideResult | None: ...
    def set(self, key: str, result: DecideResult) -> None: ...


class MemoryCache:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def get(self, key: str) -> DecideResult | None:
        raw = self._store.get(key)
        return DecideResult.model_validate_json(raw) if raw is not None else None

    def set(self, key: str, result: DecideResult) -> None:
        self._store[key] = result.model_dump_json()


class JsonlCache:
    """Append-only JSONL store; tolerates partial writes and corruption."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._memory = MemoryCache()
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                        self._memory.set(row["key"], DecideResult.model_validate(row["result"]))
                    except (KeyError, ValueError):
                        continue

    def get(self, key: str) -> DecideResult | None:
        return self._memory.get(key)

    def set(self, key: str, result: DecideResult) -> None:
        self._memory.set(key, result)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps({"key": key, "result": result.model_dump(mode="json")})
                + "\n"
            )
