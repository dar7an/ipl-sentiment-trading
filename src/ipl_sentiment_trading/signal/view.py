"""Sentiment-as-evidence view: logit(p_view) = logit(p*) + α·κ·tanh(s_a−s_b)."""

from __future__ import annotations

from math import exp, log, tanh

from ipl_sentiment_trading.config import TradingParams
from ipl_sentiment_trading.domain.models import (
    MarketQuote,
    SentimentBucket,
    SentimentSnapshot,
    Signal,
)


def _clip_prob(p: float) -> float:
    return min(max(p, 1e-9), 1.0 - 1e-9)


def logit(p: float) -> float:
    p = _clip_prob(p)
    return log(p / (1.0 - p))


def sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + exp(-z))
    ez = exp(z)
    return ez / (1.0 + ez)


def effective_n(bucket: SentimentBucket) -> float:
    """Probability-weighted volume when present (Jev), else raw count."""
    return bucket.effective_volume or float(bucket.volume)


def compute_view(
    quote: MarketQuote | None,
    sentiment: SentimentSnapshot,
    team_a: str,
    team_b: str,
    params: TradingParams,
) -> Signal:
    if quote is None or team_a not in quote.p_fair:
        return Signal(reason="no-odds")
    p_market_a = quote.p_fair[team_a]

    n_a = sentiment.team_a.volume
    n_b = sentiment.team_b.volume
    if n_a < params.min_team_comments or n_b < params.min_team_comments:
        return Signal(p_market_a=p_market_a, reason="low-volume")
    n_eff = effective_n(sentiment.team_a) + effective_n(sentiment.team_b)
    if n_eff < params.volume_floor:
        return Signal(p_market_a=p_market_a, reason="low-volume")

    diff = sentiment.team_a.mean - sentiment.team_b.mean
    shift = params.kappa * tanh(diff)
    alpha = n_eff / (n_eff + params.shrink_n0)
    log_prior = logit(p_market_a)
    p_sent_a = sigmoid(log_prior + shift)
    p_view_a = sigmoid(log_prior + alpha * shift)
    edge_a = p_view_a - p_market_a
    base = dict(
        p_market_a=p_market_a, p_sent_a=p_sent_a, p_view_a=p_view_a,
        edge_a=edge_a, alpha=alpha,
    )
    if abs(edge_a) < params.edge_threshold:
        return Signal(**base, reason="edge-below-threshold")  # type: ignore[arg-type]
    return Signal(**base, side=team_a if edge_a > 0 else team_b, reason="ok")  # type: ignore[arg-type]
