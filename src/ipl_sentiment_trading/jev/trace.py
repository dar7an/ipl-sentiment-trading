"""Decision trace: every Jev call recorded as one JSONL row.

The trace is the showcase artifact — it makes the model's judgments auditable
and feeds eval.report's cost/latency analysis.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class TraceEntry(BaseModel):
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))
    latency_ms: float = 0.0
    n_questions: int = 0
    question_keys: list[str] = Field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cache_hit: bool = False
    state_chars: int = 0
    answers_digest: dict[str, Any] = Field(default_factory=dict)


def digest_answers(answers: dict[str, Any]) -> dict[str, Any]:
    digest: dict[str, Any] = {}
    for key, ans in answers.items():
        value = getattr(ans, "choice", None)
        if value is None:
            value = getattr(ans, "noul", None)
        if value is None:
            value = getattr(ans, "score", None)
        digest[key] = value
    return digest


class JsonlTracer:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._entries: list[TraceEntry] = []
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    try:
                        self._entries.append(TraceEntry.model_validate_json(line))
                    except ValueError:
                        continue

    def record(self, entry: TraceEntry) -> None:
        self._entries.append(entry)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(entry.model_dump_json() + "\n")

    @property
    def entries(self) -> list[TraceEntry]:
        return list(self._entries)

    def totals(self) -> dict[str, Any]:
        calls = len(self._entries)
        api_calls = sum(1 for e in self._entries if not e.cache_hit)
        return {
            "calls": calls,
            "api_calls": api_calls,
            "cache_hits": calls - api_calls,
            "questions": sum(e.n_questions for e in self._entries),
            "input_tokens": sum(e.input_tokens for e in self._entries),
            "output_tokens": sum(e.output_tokens for e in self._entries),
            "latency_ms_total": round(sum(e.latency_ms for e in self._entries), 1),
        }
