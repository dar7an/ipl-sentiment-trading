from __future__ import annotations

from ipl_sentiment_trading.config import TradingParams
from ipl_sentiment_trading.domain.models import MarketQuote, SentimentBucket, SentimentSnapshot
from ipl_sentiment_trading.trading.policy import sentiment_to_view


def _quote(p_a: float, team_a="Chennai Super Kings", team_b="Mumbai Indians") -> MarketQuote:
    p_b = 1.0 - p_a
    from datetime import datetime

    return MarketQuote(
        as_of=datetime(2024, 5, 1, 19, 0, 0),
        decimal={team_a: 1.0 / p_a, team_b: 1.0 / p_b},
        p_raw={team_a: p_a, team_b: p_b},
        overround=0.0,
        p_fair={team_a: p_a, team_b: p_b},
    )


def test_mild_sentiment_does_not_invent_longshot_edge() -> None:
    """A 50/50-centered mix would call 31.0 SRH a huge edge. Log-odds must not."""
    params = TradingParams()
    sent = SentimentSnapshot(
        team_a=SentimentBucket(mean=0.15, volume=40),
        team_b=SentimentBucket(mean=0.10, volume=40),
        total_comments=80,
    )
    market = _quote(0.032, "Sunrisers Hyderabad", "Kolkata Knight Riders")
    signal = sentiment_to_view(sent, market, "Sunrisers Hyderabad", params)
    assert signal.p_view_a is not None
    assert signal.p_view_a < 0.10
    assert abs(signal.edge_a or 0) < params.edge_threshold
    assert signal.side is None
