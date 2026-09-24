"""Probability-weighted aggregation of Jev comment verdicts.

Each comment contributes with weight w = relevant·sqrt(1+upvotes); its
team attribution and bullishness enter as probabilities, not hard labels,
so a 60/40 team call counts as 60/40 — a calibrated crowd measure.
"""

from __future__ import annotations

from math import sqrt

from ipl_sentiment_trading.domain.models import (
    Comment,
    CommentVerdict,
    SentimentBucket,
    SentimentSnapshot,
)

_RELEVANT_CUT = 0.5
_ATTR_CUT = 0.5


def bullish_unit(bullish_score: float) -> float:
    """Map Jev's 1..5 bullishness score to [-1, +1] (middle level = 0)."""
    return max(-1.0, min(1.0, (bullish_score - 3.0) / 2.0))


def _bucket(
    verdicts: list[tuple[CommentVerdict, Comment]], team_key: str
) -> SentimentBucket:
    weights: list[float] = []
    units: list[float] = []
    texts: list[tuple[float, str]] = []
    volume = 0
    for v, c in verdicts:
        if v.relevant < _RELEVANT_CUT:
            continue
        p_team = v.team_probs.get(team_key, 0.0)
        if team_key != "match":
            if p_team <= 0.0 or v.team != team_key:
                continue
            if p_team >= _ATTR_CUT:
                volume += 1
        else:
            if v.team != "neutral":
                continue
            p_team = max(p_team, v.team_probs.get("neutral", 0.0))
            volume += 1
        w = v.relevant * sqrt(1.0 + max(c.upvotes, 0)) * p_team
        u = bullish_unit(v.bullish)
        weights.append(w)
        units.append(u)
        texts.append((u, " ".join(c.text.split())))
    if not weights:
        return SentimentBucket()
    mean = sum(w * u for w, u in zip(weights, units)) / sum(weights)
    eff_vol = sum(weights)
    pos = [t for u, t in sorted(texts, key=lambda x: -x[0]) if u > 0.2][:2]
    neg = [t for u, t in sorted(texts, key=lambda x: x[0]) if u < -0.2][:2]
    return SentimentBucket(
        mean=mean,
        volume=volume,
        effective_volume=eff_vol,
        upvote_weighted_mean=mean,
        sample_positive=pos,
        sample_negative=neg,
    )


def aggregate(
    verdicts: list[CommentVerdict],
    comments_by_index: dict[int, Comment],
    source: str = "jev",
    interval_verdict=None,
) -> SentimentSnapshot:
    pairs = [(v, comments_by_index[v.index]) for v in verdicts if v.index in comments_by_index]
    return SentimentSnapshot(
        team_a=_bucket(pairs, "team_a"),
        team_b=_bucket(pairs, "team_b"),
        match_level=_bucket(pairs, "match"),
        total_comments=len(comments_by_index),
        source=source,  # type: ignore[arg-type]
        verdicts=verdicts,
        interval_verdict=interval_verdict,
    )
