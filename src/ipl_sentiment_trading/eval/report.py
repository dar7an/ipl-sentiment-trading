"""eval reports: cost (from a decisions.jsonl trace) and Brier (vs frozen winner).

Brier is an eval-only use of the match winner — it measures whether the
sentiment-adjusted view beat the market's de-vigged price, retrospectively.
"""

from __future__ import annotations

import json
from pathlib import Path
from statistics import median

from ipl_sentiment_trading.domain.models import AnalysisResult


def cost_report(trace_path: str | Path) -> dict:
    calls = 0
    questions = 0
    input_tokens = 0
    cache_hits = 0
    latencies: list[float] = []
    gate_vetoes = 0
    narrator_fast = 0
    for line in Path(trace_path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        entry = json.loads(line)
        calls += 1
        questions += entry.get("n_questions") or len(entry.get("question_keys") or [])
        input_tokens += entry.get("input_tokens", 0)
        if entry.get("cache_hit"):
            cache_hits += 1
        if "latency_ms" in entry:
            latencies.append(entry["latency_ms"])
        qkeys = entry.get("question_keys") or []
        if "gate" in qkeys and (entry.get("answers_digest") or {}).get("gate", 1.0) < 0.5:
            gate_vetoes += 1
        if "drama" in qkeys:
            narrator_fast += 1
    latencies.sort()
    return {
        "calls": calls,
        "api_calls": calls - cache_hits,
        "cache_hit_rate": cache_hits / calls if calls else 0.0,
        "questions": questions,
        "input_tokens": input_tokens,
        "est_cost_usd": round(input_tokens * 1.0e-6, 4),
        "latency_p50_ms": round(median(latencies), 1) if latencies else 0.0,
        "latency_p95_ms": round(
            latencies[int(0.95 * (len(latencies) - 1))], 1
        ) if latencies else 0.0,
        "gate_vetoes": gate_vetoes,
        "drama_scores": narrator_fast,
    }


def _brier(p: float, outcome: float) -> float:
    return (p - outcome) ** 2


def brier_report(result: AnalysisResult) -> dict:
    """Mean Brier score of p_view and market p* against the frozen winner —
    separated by innings phase, plus the fill-only subset."""
    if result.winner not in {result.team_a, result.team_b}:
        return {"error": "no usable winner"}
    outcome = 1.0 if result.winner == result.team_a else 0.0
    view_scores: list[float] = []
    market_scores: list[float] = []
    by_phase: dict[str, list[tuple[float, float]]] = {}
    for iv in result.intervals:
        sig = iv.signal
        if sig.p_view_a is None or sig.p_market_a is None:
            continue
        key = "pregame" if iv.is_pregame else (
            "break" if iv.is_innings_break else f"innings{iv.cricket.innings}"
        )
        by_phase.setdefault(key, []).append((sig.p_view_a, sig.p_market_a))
        view_scores.append(_brier(sig.p_view_a, outcome))
        market_scores.append(_brier(sig.p_market_a, outcome))
    n = len(view_scores)
    phases = {
        k: {
            "n": len(v),
            "view_brier": sum(_brier(p, outcome) for p, _ in v) / len(v),
            "market_brier": sum(_brier(p, outcome) for _, p in v) / len(v),
        }
        for k, v in by_phase.items()
    }
    return {
        "n_intervals": n,
        "view_brier": sum(view_scores) / n if n else 0.0,
        "market_brier": sum(market_scores) / n if n else 0.0,
        "brier_improvement": (
            (sum(market_scores) - sum(view_scores)) / n if n else 0.0
        ),
        "by_phase": phases,
        "outcome_team": result.winner,
    }
