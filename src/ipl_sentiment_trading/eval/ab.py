"""A/B comparison: Jev judgments vs the VADER+lexicon baseline."""

from __future__ import annotations

from statistics import mean

from ipl_sentiment_trading.domain.models import CorpusMatch
from ipl_sentiment_trading.jev.types import DecideFn
from ipl_sentiment_trading.sentiment.jev_engine import JevSentimentEngine
from ipl_sentiment_trading.sentiment.vader import VaderSentimentAnalyzer


def _rank_correlation(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    rx = {v: i for i, v in enumerate(sorted(xs))}
    ry = {v: i for i, v in enumerate(sorted(ys))}
    d2 = sum((rx[x] - ry[y]) ** 2 for x, y in zip(xs, ys, strict=False))
    return 1.0 - 6.0 * d2 / (n * (n * n - 1))


def compare_engines(match: CorpusMatch, decide: DecideFn, sample_k: int = 30) -> dict:
    """Run Jev and VADER over every interval; report agreement statistics."""
    jev = JevSentimentEngine(decide, match.summary.team_a, match.summary.team_b,
                             max_candidates=sample_k)
    vader = VaderSentimentAnalyzer()
    diffs, jev_gaps, vader_gaps = [], [], []
    agree = 0
    n_both = 0
    for iv in match.intervals:
        j = jev.analyze(iv)
        v = vader.aggregate_interval(
            iv.comments, match.summary.team_a.name, match.summary.team_b.name
        )
        gj = j.team_a.mean - j.team_b.mean
        gv = v.team_a.mean - v.team_b.mean
        jev_gaps.append(gj)
        vader_gaps.append(gv)
        if j.total_comments and v.total_comments:
            n_both += 1
            diffs.append(abs(gj - gv))
            if (gj > 0) == (gv > 0):
                agree += 1
    return {
        "n_intervals": len(match.intervals),
        "n_compared": n_both,
        "mean_abs_gap": mean(diffs) if diffs else 0.0,
        "sign_agreement": agree / n_both if n_both else 0.0,
        "rank_correlation": _rank_correlation(jev_gaps, vader_gaps),
        "jev_mean_gap": mean(jev_gaps) if jev_gaps else 0.0,
        "vader_mean_gap": mean(vader_gaps) if vader_gaps else 0.0,
    }
