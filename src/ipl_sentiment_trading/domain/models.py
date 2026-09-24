"""Shared domain contract for the Jev-first rewrite.

Every module codes against these types. Do not add fields here — extend in the
owning module instead. See ARCHITECTURE.md.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# --------------------------------------------------------------------------
# Corpus (raw, frozen IPL 2024 data)
# --------------------------------------------------------------------------


class TeamRef(BaseModel):
    name: str  # canonical display name, e.g. "Royal Challengers Bengaluru"
    abbreviation: str  # "RCB"
    sportmonks_id: int | None = None


class Comment(BaseModel):
    timestamp: datetime
    text: str
    upvotes: int = 0


class Interval(BaseModel):
    """One frozen time window of a match (was 'chunk' in raw files)."""

    name: str
    start_time: datetime
    end_time: datetime
    is_pregame: bool = False
    is_innings_break: bool = False
    comments: list[Comment] = Field(default_factory=list)
    balls: list[RawBall] = Field(default_factory=list)


class RawBallScore(BaseModel):
    name: str = ""
    runs: int = 0
    four: bool = False
    six: bool = False
    bye: int = 0
    leg_bye: int = 0
    is_wicket: bool = False
    ball: bool = True  # True = legal delivery (False for wides / no-balls)
    out: bool = False


class RawBall(BaseModel):
    model_config = ConfigDict(extra="allow")

    ball: float
    updated_at: datetime | None = None
    name: str = ""  # batting team name as printed in the feed
    score: RawBallScore = Field(default_factory=RawBallScore)
    batsman: dict[str, Any] | None = None
    bowler: dict[str, Any] | None = None
    # NOTE: `forecast_data` exists on some rows and must NEVER reach live features.


class Price(BaseModel):
    team: str  # as printed in the odds feed (normalize via corpus.teams)
    decimal_odds: float


class OddsSnapshot(BaseModel):
    last_update: datetime
    prices: list[Price] = Field(default_factory=list)
    source_index: int = 0


class MatchSummary(BaseModel):
    match_id: int
    team_a: TeamRef
    team_b: TeamRef
    round: str | None = None
    date: str | None = None
    venue: str | None = None
    winner: str | None = None  # frozen result — eval/ settlement only
    winner_note: str | None = None
    missing_xi: bool = True


class CorpusMatch(BaseModel):
    summary: MatchSummary
    intervals: list[Interval]
    odds: list[OddsSnapshot]
    balls: list[RawBall]


# --------------------------------------------------------------------------
# Market
# --------------------------------------------------------------------------


class MarketQuote(BaseModel):
    as_of: datetime
    decimal: dict[str, float]  # team name -> decimal odds
    p_raw: dict[str, float]
    p_fair: dict[str, float]  # proportional de-vig
    overround: float
    is_carry_forward: bool = False  # reused snapshot, no fresh prints


# --------------------------------------------------------------------------
# Cricket
# --------------------------------------------------------------------------


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


class WindowStats(BaseModel):
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


# --------------------------------------------------------------------------
# Jev decisions (verdicts produced by the decision layer)
# --------------------------------------------------------------------------


class CommentVerdict(BaseModel):
    """Jev's typed read of one Reddit comment."""

    index: int  # position in the candidate list for the interval
    relevant: float  # noul probability: comment is about this match/cricket
    team: Literal["team_a", "team_b", "neutral"]
    team_probs: dict[str, float] = Field(default_factory=dict)
    bullish: float  # expected score (0..K) of how bullish on the favored side
    confidence: float = 0.0


class IntervalVerdict(BaseModel):
    """Jev's interval-level decisions."""

    regime: Literal["one_sided", "tense", "swing", "dead"] = "tense"
    regime_probs: dict[str, float] = Field(default_factory=dict)
    signal_quality: float = 0.0  # score: how informative is this interval's sentiment sample
    odds_stale: float = 0.0  # noul: odds snapshot looks stale/erroneous
    narrate: float = 0.0  # noul: interval merits narrative prose


class SentimentBucket(BaseModel):
    mean: float = 0.0
    volume: int = 0
    effective_volume: float = 0.0  # probability-weighted n (Jev path)
    upvote_weighted_mean: float = 0.0
    sample_positive: list[str] = Field(default_factory=list)
    sample_negative: list[str] = Field(default_factory=list)


class SentimentSnapshot(BaseModel):
    team_a: SentimentBucket = Field(default_factory=SentimentBucket)
    team_b: SentimentBucket = Field(default_factory=SentimentBucket)
    match_level: SentimentBucket = Field(default_factory=SentimentBucket)
    total_comments: int = 0
    source: Literal["jev", "vader", "none"] = "none"
    verdicts: list[CommentVerdict] = Field(default_factory=list)
    interval_verdict: IntervalVerdict | None = None


# --------------------------------------------------------------------------
# Signal / trading
# --------------------------------------------------------------------------


class Signal(BaseModel):
    p_market_a: float | None = None
    p_sent_a: float | None = None
    p_view_a: float | None = None
    edge_a: float | None = None
    alpha: float = 0.0
    side: str | None = None  # canonical team name being backed, or None
    reason: str = "no-signal"


class TradeGate(BaseModel):
    """Result of the Jev guardrail on a proposed fill."""

    approved: bool
    p_genuine: float = 1.0  # noul: edge is real signal, not noise
    skipped: bool = False  # gate not consulted (offline mode / disabled)


class Fill(BaseModel):
    interval_name: str
    as_of: datetime
    team: str
    decimal_odds: float
    stake: float
    kelly_raw: float
    reason: str
    gate: TradeGate | None = None
    settled_pnl: float | None = None


class LedgerSnapshot(BaseModel):
    cash: float
    exposure: float
    equity: float
    realized_pnl: float
    open_mtm_pnl: float
    n_open: int
    identity_cash_plus_exposure: float


# --------------------------------------------------------------------------
# Narration
# --------------------------------------------------------------------------


class NarratorRoute(BaseModel):
    model: str  # e.g. "gemma-4-26b-a4b-it" or "gemma-4-31b-it"
    drama_score: float = 0.0
    reason: str = ""


# --------------------------------------------------------------------------
# Result (the paper book)
# --------------------------------------------------------------------------


class IntervalResult(BaseModel):
    name: str
    start_time: datetime
    end_time: datetime
    is_pregame: bool
    is_innings_break: bool
    cricket: CricketState
    window: WindowStats
    market: MarketQuote | None
    sentiment: SentimentSnapshot
    signal: Signal
    fill: Fill | None
    ledger: LedgerSnapshot
    live_features: dict[str, Any] = Field(default_factory=dict)
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
    jev_usage: dict[str, Any] = Field(default_factory=dict)  # calls, tokens, latency
    sentiment_source: str = "none"
