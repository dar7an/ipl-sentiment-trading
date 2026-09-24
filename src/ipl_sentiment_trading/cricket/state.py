"""Path-dependent cricket state across a match's frozen intervals.

The tracker is cumulative: feed each interval's balls in order, then snapshot.
Partnership is NOT reset at interval boundaries — only at wickets.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ipl_sentiment_trading.corpus.teams import canonicalize_team
from ipl_sentiment_trading.cricket.legal import (
    is_boundary_ball,
    is_dot,
    is_legal_delivery,
    is_no_ball,
    is_wide,
    pct,
    run_rate,
    total_runs,
)
from ipl_sentiment_trading.domain.models import CricketState, RawBall, WindowStats

_COMMON_SURNAMES = {"singh", "kumar", "sharma", "khan", "das", "raj"}


@dataclass
class _InningsTally:
    runs: int = 0
    wickets: int = 0
    legal_balls: int = 0
    dots: int = 0
    fours: int = 0
    sixes: int = 0
    boundary_runs: int = 0


@dataclass
class CricketTracker:
    team_a: str
    team_b: str
    innings: int = 0
    batting_team: str | None = None
    partnership_runs: int = 0
    partnership_legal: int = 0
    in_break: bool = False
    tallies: dict[str, _InningsTally] = field(init=False)
    player_team: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.tallies = {self.team_a: _InningsTally(), self.team_b: _InningsTally()}

    def _other(self, team: str) -> str:
        return self.team_b if team == self.team_a else self.team_a

    def _start_innings(self, team: str) -> None:
        if self.innings <= 0:
            self.innings = 1
        elif team != self.batting_team:
            self.innings = 2
        self.batting_team = team
        self.partnership_runs = 0
        self.partnership_legal = 0
        self.in_break = False

    def note_interval_flags(self, *, is_innings_break: bool) -> None:
        if is_innings_break:
            self.in_break = True

    def _remember_players(self, ball: RawBall, batting: str) -> None:
        bowling_c = self._other(batting)
        bat = ((ball.batsman or {}).get("fullname") or "").strip()
        bowl = ((ball.bowler or {}).get("fullname") or "").strip()
        if bat:
            self.player_team[bat] = batting
            last = bat.split()[-1]
            if last and last.lower() not in _COMMON_SURNAMES:
                self.player_team.setdefault(last, batting)
        if bowl:
            self.player_team[bowl] = bowling_c
            last = bowl.split()[-1]
            if last and last.lower() not in _COMMON_SURNAMES:
                self.player_team.setdefault(last, bowling_c)

    def apply_ball(self, ball: RawBall) -> None:
        team = canonicalize_team(ball.name) or (ball.name or None)
        if team and team not in self.tallies:
            team = None  # keep stray names out of the two-team book
        if team:
            if self.innings == 0 or self.in_break or team != self.batting_team:
                self._start_innings(team)
            else:
                self.batting_team = team
                self.in_break = False
        batting = self.batting_team
        if not batting or batting not in self.tallies:
            return
        score = ball.score
        tally = self.tallies[batting]
        runs_off = total_runs(score)
        tally.runs += runs_off
        self.partnership_runs += runs_off
        if is_legal_delivery(score):
            tally.legal_balls += 1
            self.partnership_legal += 1
            if is_dot(score):
                tally.dots += 1
        if score.four:
            tally.fours += 1
        if score.six:
            tally.sixes += 1
        if is_boundary_ball(score):
            tally.boundary_runs += runs_off
        if score.is_wicket:
            tally.wickets += 1
            self.partnership_runs = 0
            self.partnership_legal = 0
        self._remember_players(ball, batting)

    def apply_balls(self, balls: list[RawBall]) -> WindowStats:
        window = WindowStats()
        for ball in balls:
            score = ball.score
            window.runs += total_runs(score)
            if is_legal_delivery(score):
                window.legal_balls += 1
                if is_dot(score):
                    window.dots += 1
            if score.is_wicket:
                window.wickets += 1
            if score.four:
                window.fours += 1
            if score.six:
                window.sixes += 1
            if is_wide(score):
                window.wides += 1
            if is_no_ball(score):
                window.no_balls += 1
            if is_boundary_ball(score):
                window.boundary_runs += total_runs(score)
            self.apply_ball(ball)
        window.run_rate = run_rate(window.runs, window.legal_balls)
        window.dot_ball_pct = pct(window.dots, window.legal_balls)
        window.boundary_ball_pct = pct(window.fours + window.sixes, window.legal_balls)
        window.boundary_run_share = pct(window.boundary_runs, window.runs)
        return window

    def snapshot(self, *, is_pregame: bool, is_innings_break: bool) -> CricketState:
        batting = self.batting_team
        bowling = self._other(batting) if batting else None
        tally = self.tallies.get(batting) if batting else None
        a = self.tallies[self.team_a]
        b = self.tallies[self.team_b]
        runs = tally.runs if tally else 0
        legal = tally.legal_balls if tally else 0
        return CricketState(
            innings=self.innings,
            batting_team=batting,
            bowling_team=bowling,
            innings_runs=runs,
            innings_wickets=tally.wickets if tally else 0,
            innings_legal_balls=legal,
            run_rate=run_rate(runs, legal),
            dot_ball_pct=pct(tally.dots, legal) if tally else 0.0,
            boundary_ball_pct=pct(tally.fours + tally.sixes, legal) if tally else 0.0,
            boundary_run_share=pct(tally.boundary_runs, runs) if tally else 0.0,
            partnership_runs=self.partnership_runs,
            partnership_legal_balls=self.partnership_legal,
            team_a_runs=a.runs,
            team_a_wickets=a.wickets,
            team_a_legal_balls=a.legal_balls,
            team_b_runs=b.runs,
            team_b_wickets=b.wickets,
            team_b_legal_balls=b.legal_balls,
            is_innings_break=is_innings_break or self.in_break,
            is_pregame=is_pregame,
        )
