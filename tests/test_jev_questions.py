from __future__ import annotations

from ipl_sentiment_trading.domain.models import Comment, TeamRef
from ipl_sentiment_trading.jev.questions import (
    comment_questions,
    comments_state,
    compaction_questions,
    interval_questions,
    route_question,
    trade_gate_question,
)
from ipl_sentiment_trading.jev.types import ChoiceQ, NoulQ, ScoreQ

A = TeamRef(name="Sunrisers Hyderabad", abbreviation="SRH")
B = TeamRef(name="Kolkata Knight Riders", abbreviation="KKR")


def _comments():
    return [
        Comment(timestamp="2024-05-26T18:30:00", text="KKR all the way", upvotes=4),
        Comment(timestamp="2024-05-26T18:31:00", text="lol SRH collapse incoming", upvotes=1),
    ]


def test_comment_questions_shape():
    q = comment_questions(_comments(), A, B)
    assert len(q) == 6
    assert isinstance(q["c0_relevant"], NoulQ)
    assert isinstance(q["c1_team"], ChoiceQ)
    assert set(q["c0_team"].criteria) == {"team_a", "team_b", "neutral"}
    assert isinstance(q["c0_bullish"], ScoreQ)
    assert len(q["c0_bullish"].criteria) == 5
    assert "[0]" in q["c0_relevant"].instructions


def test_comments_state_numbers_and_trims():
    state = comments_state(_comments(), A, B)
    assert "[0]" in state and "[1]" in state
    assert "Sunrisers Hyderabad" in state and "KKR" in state


def test_interval_questions_keys():
    q = interval_questions(A, B)
    assert set(q) == {"regime", "signal_quality", "odds_stale", "narrate"}
    assert isinstance(q["regime"], ChoiceQ)
    assert set(q["regime"].criteria) == {"one_sided", "tense", "swing", "dead"}


def test_gate_route_compaction():
    assert set(trade_gate_question()) == {"gate"}
    assert set(route_question()) == {"drama"}
    cq = compaction_questions(3)
    assert set(cq) == {"f0", "f1", "f2"}
    assert set(cq["f0"].criteria) == {"keep", "trim", "drop"}
