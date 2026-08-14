from __future__ import annotations

from math import exp, log, tanh

from ipl_sentiment_trading.config import TradingParams
from ipl_sentiment_trading.domain.models import MarketQuote, SentimentSnapshot, Signal


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


def sentiment_to_view(
    sentiment: SentimentSnapshot,
    market: MarketQuote | None,
    team_a: str,
    params: TradingParams,
) -> Signal:
    if market is None or team_a not in market.p_fair:
        return Signal(reason="no-market")
    n_a = sentiment.team_a.volume
    n_b = sentiment.team_b.volume
    n = n_a + n_b
    p_market_a = market.p_fair[team_a]
    if n_a < params.min_team_comments or n_b < params.min_team_comments:
        return Signal(p_market_a=p_market_a, reason="insufficient-team-volume")
    if n < params.volume_floor:
        return Signal(p_market_a=p_market_a, reason="insufficient-volume")

    diff = sentiment.team_a.mean - sentiment.team_b.mean
    shift = params.kappa * tanh(diff)
    alpha = n / (n + params.shrink_n0)
    log_prior = logit(p_market_a)
    p_sent_a = sigmoid(log_prior + shift)
    p_view_a = sigmoid(log_prior + alpha * shift)
    edge_a = p_view_a - p_market_a
    if abs(edge_a) < params.edge_threshold:
        return Signal(
            p_market_a=p_market_a,
            p_sent_a=p_sent_a,
            p_view_a=p_view_a,
            edge_a=edge_a,
            alpha=alpha,
            reason="below-edge-threshold",
        )
    return Signal(
        p_market_a=p_market_a,
        p_sent_a=p_sent_a,
        p_view_a=p_view_a,
        edge_a=edge_a,
        alpha=alpha,
        side="A" if edge_a > 0 else "B",
        reason="edge",
    )


def kelly_fraction(p_win: float, decimal_odds: float) -> float:
    if decimal_odds <= 1.0 or not 0.0 < p_win < 1.0:
        return 0.0
    b = decimal_odds - 1.0
    f_star = (p_win * decimal_odds - 1.0) / b
    return max(0.0, f_star)
