from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TeamRef(BaseModel):
    name: str
    abbreviation: str
    sportmonks_id: int | None = None


class Price(BaseModel):
    team: str
    decimal_odds: float


class OddsSnapshot(BaseModel):
    last_update: datetime
    prices: list[Price]
    source_index: int = 0


class MarketQuote(BaseModel):
    as_of: datetime
    decimal: dict[str, float]
    p_raw: dict[str, float]
    overround: float
    p_fair: dict[str, float]


class CricketState(BaseModel):
    innings: int = 0
    batting_team: str | None = None
    bowling_team: str | None = None
    innings_runs: int = 0
    innings_wickets: int = 0
    innings_legal_balls: int = 0
    run_rate: float = 0.0
    dot_ball_pct: float = 0.0
    boundary_ball_pct: float = 0.0
    boundary_run_share: float = 0.0
    partnership_runs: int = 0
    partnership_legal_balls: int = 0
    team_a_runs: int = 0
    team_a_wickets: int = 0
    team_a_legal_balls: int = 0
    team_b_runs: int = 0
    team_b_wickets: int = 0
    team_b_legal_balls: int = 0
    is_innings_break: bool = False
    is_pregame: bool = False

    def overs_str(self) -> str:
        balls = self.innings_legal_balls
        return f"{balls // 6}.{balls % 6}"


class IntervalWindowStats(BaseModel):
    runs: int = 0
    legal_balls: int = 0
    wickets: int = 0
    dots: int = 0
    fours: int = 0
    sixes: int = 0
    wides: int = 0
    no_balls: int = 0
    boundary_runs: int = 0
    run_rate: float = 0.0
    dot_ball_pct: float = 0.0
    boundary_ball_pct: float = 0.0
    boundary_run_share: float = 0.0


class SentimentBucket(BaseModel):
    mean: float = 0.0
    volume: int = 0
    upvote_weighted_mean: float = 0.0
    sample_positive: list[str] = Field(default_factory=list)
    sample_negative: list[str] = Field(default_factory=list)


class SentimentSnapshot(BaseModel):
    team_a: SentimentBucket = Field(default_factory=SentimentBucket)
    team_b: SentimentBucket = Field(default_factory=SentimentBucket)
    match_level: SentimentBucket = Field(default_factory=SentimentBucket)
    total_comments: int = 0


class Signal(BaseModel):
    p_market_a: float | None = None
    p_sent_a: float | None = None
    p_view_a: float | None = None
    edge_a: float | None = None
    alpha: float = 0.0
    side: str | None = None
    reason: str = "no-signal"


class Fill(BaseModel):
    interval_name: str
    as_of: datetime
    team: str
    decimal_odds: float
    stake: float
    kelly_raw: float
    reason: str
    settled_pnl: float | None = None


class LedgerSnapshot(BaseModel):
    cash: float
    exposure: float
    equity: float
    realized_pnl: float
    open_mtm_pnl: float
    n_open: int
    identity_cash_plus_exposure: float


class IntervalResult(BaseModel):
    name: str
    start_time: datetime
    end_time: datetime
    is_pregame: bool
    is_innings_break: bool
    cricket: CricketState
    window: IntervalWindowStats
    market: MarketQuote | None
    sentiment: SentimentSnapshot
    signal: Signal
    fill: Fill | None
    ledger: LedgerSnapshot
    live_features: dict[str, Any]
    narrative: str | None = None


class AnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match_id: int
    team_a: str
    team_b: str
    team_a_abbr: str
    team_b_abbr: str
    date: str | None = None
    venue: str | None = None
    round: str | None = None
    winner: str | None = None
    winner_note: str | None = None
    starting_bankroll: float
    ending_equity: float
    realized_pnl: float
    max_drawdown: float
    max_drawdown_abs: float
    n_fills: int
    n_hits: int
    hit_rate: float | None = None
    narrative_provider: str = "off"
    intervals: list[IntervalResult]
    fills: list[Fill]
    formula_notes: dict[str, str]
    missing_xi: bool = True
    corpus_gaps: list[int] = Field(default_factory=lambda: [63, 66, 70])
