from __future__ import annotations

import json
import os

import httpx
import pytest

from ipl_sentiment_trading.jev.cache import JsonlCache, MemoryCache
from ipl_sentiment_trading.jev.client import (
    OFFICIAL_URL,
    PROXY_URL,
    DecideClient,
    JevError,
)
from ipl_sentiment_trading.jev.trace import JsonlTracer
from ipl_sentiment_trading.jev.types import DecideResult, NoulQ


def _payload() -> dict:
    return {
        "model": "jev-1.13.0",
        "answers": {"ok": {"type": "noul", "noul": 0.9}},
        "usage": {"input_tokens": 10, "output_tokens": 2},
    }


def _client(handler, **kwargs):
    transport = httpx.MockTransport(handler)
    kwargs.setdefault("api_key", "test-key")
    kwargs.setdefault("max_retries", 3)
    return DecideClient(transport=transport, **kwargs)


def test_posts_model_state_questions(monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_payload())

    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.delenv("JEV_API_KEY", raising=False)
    monkeypatch.delenv("JEV_BASE_URL", raising=False)
    client = _client(handler)
    out = client.decide("state text", {"ok": NoulQ(instructions="fine?")})
    assert seen["url"] == OFFICIAL_URL
    assert seen["auth"] == "Bearer test-key"
    assert seen["body"]["model"] == "jev-latest"
    assert seen["body"]["questions"] == {
        "ok": {"type": "noul", "instructions": "fine?"}
    }
    assert out.answers["ok"].noul == 0.9
    assert out.usage.input_tokens == 10


def test_proxy_key_defaults_to_proxy_url():
    client = DecideClient(
        api_key="jv_live_abc", transport=httpx.MockTransport(lambda r: httpx.Response(200, json=_payload()))
    )
    assert client.base_url == PROXY_URL


def test_retry_on_429_then_success(monkeypatch):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, headers={"retry-after": "0"})
        return httpx.Response(200, json=_payload())

    monkeypatch.setattr("time.sleep", lambda *_: None)
    client = _client(handler)
    out = client.decide("s", {"ok": NoulQ(instructions="?")})
    assert calls["n"] == 3
    assert out.answers["ok"].noul == 0.9


def test_401_raises_jev_error():
    client = _client(lambda r: httpx.Response(401, json={"detail": "bad key"}))
    with pytest.raises(JevError) as exc:
        client.decide("s", {"ok": NoulQ(instructions="?")})
    assert exc.value.status == 401


def test_cache_hit_skips_network(tmp_path):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=_payload())

    tracer = JsonlTracer(tmp_path / "trace.jsonl")
    cache = MemoryCache()
    client = _client(handler, cache=cache, tracer=tracer)
    q = {"ok": NoulQ(instructions="?")}
    client.decide("s", q)
    client.decide("s", q)
    assert calls["n"] == 1
    totals = tracer.totals()
    assert totals["calls"] == 2
    assert totals["api_calls"] == 1
    assert totals["cache_hits"] == 1


def test_jsonl_cache_persists(tmp_path):
    path = tmp_path / "cache.jsonl"
    cache = JsonlCache(path)
    cache.set("k", DecideResult.model_validate(_payload()))
    fresh = JsonlCache(path)
    assert fresh.get("k").answers["ok"].noul == 0.9


def test_missing_key_raises():
    for var in ("TYPESAFE_API_KEY", "JEV_API_KEY"):
        os.environ.pop(var, None)
    with pytest.raises(JevError):
        DecideClient()
