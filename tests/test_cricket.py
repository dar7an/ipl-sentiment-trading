from __future__ import annotations

from ipl_sentiment_trading.corpus.loader import load_match
from ipl_sentiment_trading.cricket.legal import (
    is_dot,
    is_legal_delivery,
    is_no_ball,
    is_wide,
)
from ipl_sentiment_trading.cricket.state import CricketTracker
from ipl_sentiment_trading.domain.models import RawBall, RawBallScore


def _ball(runs=1, wicket=False, four=False, six=False, name="", legal=True, team="A"):
    return RawBall(
        ball=0.1,
        name=team,
        score=RawBallScore(
            name=name, runs=runs, is_wicket=wicket, four=four, six=six, ball=legal
        ),
    )


def test_legal_delivery_rules():
    assert is_legal_delivery(_ball().score)
    assert not is_legal_delivery(_ball(name="Wide", legal=False).score)
    assert not is_legal_delivery(_ball(name="No Ball", legal=False).score)
    assert is_wide(_ball(name="Wide", legal=False).score)
    assert is_no_ball(_ball(name="No Ball", legal=False).score)
    assert is_dot(_ball(runs=0).score)
    assert is_dot(_ball(runs=0, wicket=True).score)  # wicket ball with 0 runs is a dot
    assert not is_dot(_ball(runs=0, name="Wide", legal=False).score)


def test_tracker_accumulates_and_switches_innings():
    t = CricketTracker("A", "B")
    t.apply_balls([_ball(runs=4, four=True, team="A"), _ball(runs=2, team="A")])
    s = t.snapshot(is_pregame=False, is_innings_break=False)
    assert s.innings == 1 and s.batting_team == "A"
    assert s.innings_runs == 6 and s.innings_legal_balls == 2
    assert s.partnership_runs == 6
    t.apply_balls([_ball(runs=0, wicket=True, team="A")])
    assert t.snapshot(is_pregame=False, is_innings_break=False).partnership_runs == 0
    s = t.snapshot(is_pregame=False, is_innings_break=False)
    assert s.innings_wickets == 1
    t.apply_balls([_ball(runs=1, team="B")])
    s = t.snapshot(is_pregame=False, is_innings_break=False)
    assert s.innings == 2 and s.batting_team == "B"
    assert s.team_a_runs == 6 and s.team_b_runs == 1


def test_match_74_first_innings_total():
    m = load_match(74)
    t = CricketTracker(m.summary.team_a.name, m.summary.team_b.name)
    # Cumulative state must come from the complete balls feed, not the
    # chunk-embedded subsets.
    t.apply_balls(sorted(m.balls, key=lambda b: (b.updated_at or b.ball, b.ball)))
    final = t.snapshot(is_pregame=False, is_innings_break=False)
    # SRH 113 all out; KKR 114/2 in the 2024 final (byes + leg-byes included).
    assert final.team_a_runs == 113
    assert final.team_b_runs == 114
    assert final.team_a_wickets == 10
    assert final.team_b_wickets == 2
    assert final.innings == 2
