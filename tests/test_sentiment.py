from __future__ import annotations

from datetime import datetime

from ipl_sentiment_trading.domain.models import (
    Comment,
    Interval,
    TeamRef,
)
from ipl_sentiment_trading.jev.types import (
    ChoiceA,
    DecideResult,
    NoulA,
    ScoreA,
    Usage,
)
from ipl_sentiment_trading.sentiment.candidates import select_candidates
from ipl_sentiment_trading.sentiment.jev_engine import JevSentimentEngine
from ipl_sentiment_trading.sentiment.vader import VaderSentimentAnalyzer

TEAM_A = TeamRef(name="Sunrisers Hyderabad", abbreviation="SRH", sportmonks_id=9)
TEAM_B = TeamRef(name="Kolkata Knight Riders", abbreviation="KKR", sportmonks_id=4)


def _comments():
    return [
        Comment(timestamp=datetime(2024, 5, 26, 20, 0), text="SRH are collapsing, what a spell from KKR!", upvotes=30),
        Comment(timestamp=datetime(2024, 5, 26, 20, 1), text="KKR cruising to the title, glorious", upvotes=25),
        Comment(timestamp=datetime(2024, 5, 26, 20, 2), text="random link spam click here", upvotes=0),
        Comment(timestamp=datetime(2024, 5, 26, 20, 3), text="SRH will come back, Cummins is unreal", upvotes=15),
    ]


def _fake_decide(approved=True):
    calls = []

    def decide(state, questions):
        calls.append((state, questions))
        answers = {}
        answers["c0_relevant"] = NoulA(type="noul", noul=0.95)
        answers["c0_team"] = ChoiceA(
            type="choice", choice="team_b", confidence=0.8,
            probabilities={"team_a": 0.1, "team_b": 0.85, "neutral": 0.05},
        )
        answers["c0_bullish"] = ScoreA(type="score", score=4.6, confidence=0.9)
        answers["c1_relevant"] = NoulA(type="noul", noul=0.9)
        answers["c1_team"] = ChoiceA(
            type="choice", choice="team_b", confidence=0.9,
            probabilities={"team_a": 0.05, "team_b": 0.9, "neutral": 0.05},
        )
        answers["c1_bullish"] = ScoreA(type="score", score=4.2, confidence=0.9)
        answers["c2_relevant"] = NoulA(type="noul", noul=0.1)
        answers["c2_team"] = ChoiceA(
            type="choice", choice="neutral", confidence=0.5,
            probabilities={"team_a": 0.1, "team_b": 0.1, "neutral": 0.8},
        )
        answers["c2_bullish"] = ScoreA(type="score", score=3.0, confidence=0.5)
        answers["c3_relevant"] = NoulA(type="noul", noul=0.8)
        answers["c3_team"] = ChoiceA(
            type="choice", choice="team_a", confidence=0.7,
            probabilities={"team_a": 0.75, "team_b": 0.15, "neutral": 0.1},
        )
        answers["c3_bullish"] = ScoreA(type="score", score=3.4, confidence=0.7)
        answers["regime"] = ChoiceA(
            type="choice", choice="one_sided", confidence=0.7,
            probabilities={"one_sided": 0.6, "tense": 0.3, "swing": 0.05, "dead": 0.05},
        )
        answers["signal_quality"] = ScoreA(type="score", score=3.8, confidence=0.8)
        answers["odds_stale"] = NoulA(type="noul", noul=0.1)
        answers["narrate"] = NoulA(type="noul", noul=0.7)
        if "gate" in questions:
            answers["gate"] = NoulA(type="noul", noul=0.9 if approved else 0.1)
        return DecideResult(model="fake", answers=answers, usage=Usage(input_tokens=10))

    decide.calls = calls
    return decide


def _interval():
    return Interval(
        name="18-20 ov", start_time=datetime(2024, 5, 26, 20, 0),
        end_time=datetime(2024, 5, 26, 20, 10), comments=_comments(),
    )


def test_select_candidates_dedupes_and_orders():
    comments = _comments() + [Comment(timestamp=datetime(2024, 5, 26, 20, 4), text="SRH are collapsing, what a spell from KKR!", upvotes=3)]
    sel = select_candidates(comments, k=10)
    assert [i for i, _ in sel] == [0, 1, 2, 3]  # dup removed, chrono order


def test_jev_engine_one_call_verdicts():
    decide = _fake_decide()
    engine = JevSentimentEngine(decide, TEAM_A, TEAM_B)
    snap = engine.analyze(_interval())
    assert len(decide.calls) == 1
    assert snap.source == "jev"
    assert snap.interval_verdict.regime == "one_sided"
    assert snap.team_b.volume == 2
    assert snap.team_a.volume == 1
    assert snap.team_b.mean > 0.5
    assert snap.team_b.effective_volume > snap.team_a.effective_volume
    assert snap.verdicts[2].relevant == 0.1


def test_vader_scores_cricket_lexicon():
    v = VaderSentimentAnalyzer()
    assert v.score_text("what a six!!") > 0.5
    assert v.score_text("golden duck, gone for nothing") < -0.5
    snap = v.aggregate_interval(_comments(), TEAM_A.name, TEAM_B.name)
    assert snap.source == "vader"
    assert snap.total_comments == 4
