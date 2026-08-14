from __future__ import annotations

from ipl_sentiment_trading.cricket.legal import is_dot, is_legal_delivery, run_rate
from ipl_sentiment_trading.cricket.state import CricketTracker
from ipl_sentiment_trading.data.schema import FrozenBall, FrozenScore


def _score(**kwargs) -> FrozenScore:
    return FrozenScore.model_validate(kwargs)


def test_dot_includes_legal_wicket() -> None:
    wicket = _score(name="Clean Bowled", runs=0, is_wicket=True, ball=True)
    four = _score(name="FOUR", runs=4, four=True, ball=True)
    wide = _score(name="1 Wide", runs=1, ball=False)
    assert is_legal_delivery(wicket)
    assert is_dot(wicket)
    assert not is_dot(four)
    assert not is_legal_delivery(wide)
    tracker = CricketTracker("Sunrisers Hyderabad", "Kolkata Knight Riders")
    balls = [
        FrozenBall(name="Sunrisers Hyderabad", score=wicket, ball=0.1),
        FrozenBall(name="Sunrisers Hyderabad", score=four, ball=0.2),
    ]
    window = tracker.apply_balls(balls)
    assert window.legal_balls == 2
    assert window.dots == 1
    assert window.dot_ball_pct == 0.5
    assert window.wickets == 1


def test_partnership_spans_chunks_until_wicket() -> None:
    tracker = CricketTracker("Sunrisers Hyderabad", "Kolkata Knight Riders")
    legal_run = _score(name="1 Run", runs=1, ball=True)
    first = [FrozenBall(name="Sunrisers Hyderabad", score=legal_run, ball=1.1) for _ in range(4)]
    tracker.apply_balls(first)
    state = tracker.snapshot(is_pregame=False, is_innings_break=False)
    assert state.partnership_runs == 4
    second = [FrozenBall(name="Sunrisers Hyderabad", score=legal_run, ball=1.5) for _ in range(3)]
    tracker.apply_balls(second)
    state = tracker.snapshot(is_pregame=False, is_innings_break=False)
    assert state.partnership_runs == 7
    wicket = FrozenBall(
        name="Sunrisers Hyderabad",
        score=_score(name="Catch Out", runs=0, is_wicket=True, ball=True),
        ball=2.1,
    )
    tracker.apply_balls([wicket])
    state = tracker.snapshot(is_pregame=False, is_innings_break=False)
    assert state.partnership_runs == 0
    assert state.innings_runs == 7


def test_run_rate_zero_legal_balls_is_zero() -> None:
    assert run_rate(12, 0) == 0.0
    tracker = CricketTracker("A", "B")
    wide = FrozenBall(
        name="A",
        score=_score(name="1 Wide", runs=1, ball=False),
        ball=0.1,
    )
    window = tracker.apply_balls([wide])
    assert window.legal_balls == 0
    assert window.run_rate == 0.0
    state = tracker.snapshot(is_pregame=False, is_innings_break=False)
    assert state.run_rate == 0.0


def test_no_ball_is_not_legal_even_if_score_ball_true() -> None:
    nb = _score(name="1 No Ball + Six", runs=7, six=True, ball=True)
    assert not is_legal_delivery(nb)
    assert not is_dot(nb)


def test_innings_change_from_batting_team_not_ball_six() -> None:
    tracker = CricketTracker("Sunrisers Hyderabad", "Kolkata Knight Riders")
    six_over = FrozenBall(
        name="Sunrisers Hyderabad",
        score=_score(name="No Run", runs=0, ball=True),
        ball=6.0,
    )
    tracker.apply_balls([six_over])
    assert tracker.innings == 1
    tracker.note_interval_flags(is_innings_break=True)
    second = FrozenBall(
        name="Kolkata Knight Riders",
        score=_score(name="1 Run", runs=1, ball=True),
        ball=0.1,
    )
    tracker.apply_balls([second])
    assert tracker.innings == 2
    assert tracker.batting_team == "Kolkata Knight Riders"
    assert tracker.partnership_runs == 1
