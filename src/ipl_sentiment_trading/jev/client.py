"""HTTP client for the Jev decision API.

Official endpoint: POST https://api.typesafe.ai/v1/systemone with a TypeSafe key.
Metered proxy:     POST https://jevtypesafeai.com/api/v1/decide with a jv_live_* key.
"""

from __future__ import annotations

import contextlib
import os
import random
import time
from typing import Any, Self

import httpx

from ipl_sentiment_trading.jev.cache import Cache, cache_key
from ipl_sentiment_trading.jev.trace import JsonlTracer, TraceEntry, digest_answers
from ipl_sentiment_trading.jev.types import DecideResult, Question

OFFICIAL_URL = "https://api.typesafe.ai/v1/systemone"
PROXY_URL = "https://jevtypesafeai.com/api/v1/decide"
DEFAULT_MODEL = "jev-latest"


class JevError(RuntimeError):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def _resolve_api_key(explicit: str | None) -> str | None:
    return explicit or os.getenv("TYPESAFE_API_KEY") or os.getenv("JEV_API_KEY")


def _resolve_base_url(explicit: str | None, api_key: str | None) -> str:
    if explicit:
        return explicit
    env = os.getenv("JEV_BASE_URL")
    if env:
        return env
    if api_key and api_key.startswith("jv_live_"):
        return PROXY_URL
    if api_key and os.getenv("JEV_API_KEY") and not os.getenv("TYPESAFE_API_KEY"):
        return PROXY_URL
    return OFFICIAL_URL


class DecideClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        cache: Cache | None = None,
        tracer: Any = None,
        timeout: float = 30.0,
        max_retries: int = 4,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.api_key = _resolve_api_key(api_key)
        if not self.api_key:
            raise JevError(
                "No Jev API key — set TYPESAFE_API_KEY or JEV_API_KEY", status=None
            )
        self.base_url = _resolve_base_url(base_url, self.api_key)
        self.model = model or os.getenv("JEV_MODEL", DEFAULT_MODEL)
        self.cache = cache
        self.tracer = tracer
        self.max_retries = max_retries
        self._client = httpx.Client(
            timeout=timeout,
            transport=transport,
            headers={"Authorization": f"Bearer {self.api_key}"},
        )

    def decide(self, state: str, questions: dict[str, Question]) -> DecideResult:
        key = cache_key(self.model, state, questions)
        started = time.monotonic()
        if self.cache is not None:
            hit = self.cache.get(key)
            if hit is not None:
                self._record(state, questions, hit, started, cache_hit=True)
                return hit
        body = {
            "model": self.model,
            "state": state,
            "questions": {k: q.model_dump() for k, q in questions.items()},
        }
        result = self._post_with_retries(body)
        if self.cache is not None:
            self.cache.set(key, result)
        self._record(state, questions, result, started, cache_hit=False)
        return result

    def _post_with_retries(self, body: dict[str, Any]) -> DecideResult:
        attempt = 0
        while True:
            try:
                resp = self._client.post(self.base_url, json=body)
            except httpx.HTTPError as exc:
                attempt += 1
                if attempt > self.max_retries:
                    raise JevError(f"Jev transport error after {attempt} tries: {exc}") from exc
                self._sleep(attempt)
                continue
            if resp.status_code == 429 or resp.status_code >= 500:
                attempt += 1
                if attempt > self.max_retries:
                    raise JevError(
                        f"Jev HTTP {resp.status_code} after {attempt} tries",
                        status=resp.status_code,
                    )
                self._sleep(attempt, resp)
                continue
            if resp.status_code >= 400:
                raise JevError(
                    f"Jev HTTP {resp.status_code}: {resp.text[:300]}",
                    status=resp.status_code,
                )
            try:
                return DecideResult.model_validate(resp.json())
            except ValueError as exc:
                raise JevError(f"Jev returned unparseable payload: {exc}") from exc

    def _sleep(self, attempt: int, resp: httpx.Response | None = None) -> None:
        wait = min(2**attempt + random.random(), 30.0)
        if resp is not None:
            with contextlib.suppress(ValueError):
                wait = max(wait, float(resp.headers.get("retry-after", 0)))
        time.sleep(wait)

    def _record(
        self,
        state: str,
        questions: dict[str, Question],
        result: DecideResult,
        started: float,
        cache_hit: bool,
    ) -> None:
        if self.tracer is None:
            return
        self.tracer.record(
            TraceEntry(
                latency_ms=(time.monotonic() - started) * 1000.0,
                n_questions=len(questions),
                question_keys=sorted(questions),
                input_tokens=result.usage.input_tokens,
                output_tokens=result.usage.output_tokens,
                cache_hit=cache_hit,
                state_chars=len(state),
                answers_digest=digest_answers(result.answers),
            )
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def open_traced_client(
    trace_path: str | None,
    cache_path: str | None = None,
    **kwargs: Any,
) -> DecideClient:
    """Convenience: client with a JSONL trace (and optional persistent cache)."""
    from ipl_sentiment_trading.jev.cache import JsonlCache

    tracer = JsonlTracer(trace_path) if trace_path else None
    cache = JsonlCache(cache_path) if cache_path else None
    return DecideClient(tracer=tracer, cache=cache, **kwargs)
