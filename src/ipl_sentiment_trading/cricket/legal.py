"""Legal-ball accounting from the frozen Sportmonks-shaped score records."""

from __future__ import annotations

from ipl_sentiment_trading.domain.models import RawBallScore


def score_name(score: RawBallScore) -> str:
    return (score.name or "").lower()


def is_wide(score: RawBallScore) -> bool:
    return "wide" in score_name(score)


def is_no_ball(score: RawBallScore) -> bool:
    return "no ball" in score_name(score)


def is_legal_delivery(score: RawBallScore) -> bool:
    """Wides and no-balls do not count in the over, regardless of score.ball."""
    if is_wide(score) or is_no_ball(score):
        return False
    return bool(score.ball)


def total_runs(score: RawBallScore) -> int:
    """All runs scored off the delivery: bat runs + byes + leg-byes.
    `score.runs` in the corpus already contains wide/no-ball penalty runs."""
    return score.runs + score.bye + score.leg_bye


def is_dot(score: RawBallScore) -> bool:
    """Legal 0-run balls, including wickets."""
    return is_legal_delivery(score) and total_runs(score) == 0


def is_boundary_ball(score: RawBallScore) -> bool:
    return bool(score.four or score.six)


def boundary_runs(score: RawBallScore) -> int:
    return score.runs if is_boundary_ball(score) else 0


def run_rate(runs: int, legal_balls: int) -> float:
    if legal_balls <= 0:
        return 0.0
    return runs / (legal_balls / 6.0)


def pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator
