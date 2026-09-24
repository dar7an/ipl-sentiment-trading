"""Jev sentiment engine — one batched decision call per interval.

Replaces "run a lexicon over every comment" with a typed judgment per
comment (relevance, side favored, bullishness) plus interval-level
decisions (regime, signal quality, stale odds, narrate), all in a single
`decide` call so questions share the state prefix.
"""

from __future__ import annotations

from ipl_sentiment_trading.domain.models import (
    Comment,
    CommentVerdict,
    CricketState,
    Interval,
    IntervalVerdict,
    MarketQuote,
    SentimentSnapshot,
    TeamRef,
)
from ipl_sentiment_trading.jev.questions import (
    comment_questions,
    comments_state,
    interval_questions,
)
from ipl_sentiment_trading.jev.types import ChoiceA, DecideFn, NoulA, ScoreA
from ipl_sentiment_trading.sentiment.aggregate import aggregate
from ipl_sentiment_trading.sentiment.candidates import select_candidates


def _argmax_key(probs: dict[str, float]) -> str:
    return max(probs, key=probs.get) if probs else "neutral"  # type: ignore[arg-type]


def _interval_state(
    candidates: list[Comment],
    team_a: TeamRef,
    team_b: TeamRef,
    cricket: CricketState | None,
    market: MarketQuote | None,
) -> str:
    state = comments_state(candidates, team_a, team_b)
    ctx = []
    if cricket is not None and cricket.innings > 0:
        ctx.append(
            f"Match situation: innings {cricket.innings}, "
            f"{cricket.batting_team or '?'} batting, "
            f"{cricket.innings_runs}/{cricket.innings_wickets} "
            f"off {cricket.innings_legal_balls} legal balls."
        )
    if market is not None:
        ctx.append(
            "De-vigged market probabilities: "
            + ", ".join(f"{t} {p:.1%}" for t, p in market.p_fair.items())
            + f" (overround {market.overround:.1%})."
        )
    if ctx:
        state += "\n\n" + "\n".join(ctx)
    return state


class JevSentimentEngine:
    def __init__(
        self,
        decide: DecideFn,
        team_a: TeamRef,
        team_b: TeamRef,
        max_candidates: int = 30,
    ) -> None:
        self.decide = decide
        self.team_a = team_a
        self.team_b = team_b
        self.max_candidates = max_candidates

    def analyze(
        self,
        interval: Interval,
        cricket: CricketState | None = None,
        market: MarketQuote | None = None,
    ) -> SentimentSnapshot:
        selected = select_candidates(interval.comments, self.max_candidates)
        if not selected:
            return SentimentSnapshot(
                total_comments=len(interval.comments), source="jev"
            )
        cand_comments = [c for _, c in selected]
        state = _interval_state(cand_comments, self.team_a, self.team_b, cricket, market)
        questions = {
            **comment_questions(cand_comments, self.team_a, self.team_b),
            **interval_questions(self.team_a, self.team_b),
        }
        result = self.decide(state, questions)
        answers = result.answers

        verdicts: list[CommentVerdict] = []
        by_index = {orig_i: c for orig_i, c in selected}
        for pos, (orig_i, _c) in enumerate(selected):
            rel_a = answers.get(f"c{pos}_relevant")
            team_a_ = answers.get(f"c{pos}_team")
            bull_a = answers.get(f"c{pos}_bullish")
            relevant = rel_a.noul if isinstance(rel_a, NoulA) else 0.0
            team_probs = team_a_.probabilities if isinstance(team_a_, ChoiceA) else {}
            bullish = bull_a.score if isinstance(bull_a, ScoreA) else 3.0
            verdicts.append(
                CommentVerdict(
                    index=orig_i,
                    relevant=relevant,
                    team=_argmax_key(team_probs),
                    team_probs=team_probs,
                    bullish=bullish,
                    confidence=getattr(team_a_, "confidence", 0.0) or 0.0,
                )
            )

        regime_a = answers.get("regime")
        quality_a = answers.get("signal_quality")
        stale_a = answers.get("odds_stale")
        narrate_a = answers.get("narrate")
        interval_verdict = IntervalVerdict(
            regime=regime_a.choice if isinstance(regime_a, ChoiceA) else "tense",
            regime_probs=regime_a.probabilities if isinstance(regime_a, ChoiceA) else {},
            signal_quality=quality_a.score if isinstance(quality_a, ScoreA) else 0.0,
            odds_stale=stale_a.noul if isinstance(stale_a, NoulA) else 0.0,
            narrate=narrate_a.noul if isinstance(narrate_a, NoulA) else 0.0,
        )
        return aggregate(verdicts, by_index, source="jev", interval_verdict=interval_verdict)
