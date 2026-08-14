"""Legal-ball accounting from the frozen Sportmonks-shaped score records."""

from __future__ import annotations

from ipl_sentiment_trading.data.schema import FrozenScore


def score_name(score: FrozenScore) -> str:
    return (score.name or "").lower()


def is_wide(score: FrozenScore) -> bool:
    return "wide" in score_name(score)


def is_no_ball(score: FrozenScore) -> bool:
    return "no ball" in score_name(score)


def is_legal_delivery(score: FrozenScore) -> bool:
    """Wides and no-balls do not count in the over, regardless of score.ball."""
    if is_wide(score) or is_no_ball(score):
        return False
    return bool(score.ball)


def is_dot(score: FrozenScore) -> bool:
    """Legal 0-run balls, including wickets."""
    return is_legal_delivery(score) and score.runs == 0


def is_boundary_ball(score: FrozenScore) -> bool:
    return bool(score.four or score.six)


def run_rate(runs: int, legal_balls: int) -> float:
    if legal_balls <= 0:
        return 0.0
    return runs / (legal_balls / 6.0)


def pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator
