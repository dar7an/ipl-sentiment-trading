from __future__ import annotations

from datetime import datetime

from ipl_sentiment_trading.domain.models import (
    CricketState,
    IntervalWindowStats,
    MarketQuote,
    SentimentSnapshot,
    Signal,
)

LIVE_FEATURE_KEYS = (
    "interval",
    "start_time",
    "end_time",
    "is_pregame",
    "is_innings_break",
    "team_a",
    "team_b",
    "innings",
    "batting_team",
    "bowling_team",
    "innings_runs",
    "innings_wickets",
    "innings_legal_balls",
    "overs",
    "run_rate",
    "dot_ball_pct",
    "boundary_ball_pct",
    "boundary_run_share",
    "partnership_runs",
    "partnership_legal_balls",
    "window_runs",
    "window_legal_balls",
    "window_wickets",
    "window_dot_ball_pct",
    "decimal_a",
    "decimal_b",
    "p_raw_a",
    "p_raw_b",
    "p_fair_a",
    "p_fair_b",
    "overround",
    "sent_mean_a",
    "sent_mean_b",
    "sent_vol_a",
    "sent_vol_b",
    "sent_match_mean",
    "sent_match_vol",
    "p_sent_a",
    "p_view_a",
    "edge_a",
    "alpha",
    "signal_reason",
)

FORBIDDEN_FEATURE_SUBSTR = (
    "winner",
    "forecast",
    "margin",
    "won by",
    "winner_team",
    "final_score",
)


def build_live_features(
    *,
    interval_name: str,
    start: datetime,
    end: datetime,
    is_pregame: bool,
    is_innings_break: bool,
    team_a: str,
    team_b: str,
    cricket: CricketState,
    window: IntervalWindowStats,
    market: MarketQuote | None,
    sentiment: SentimentSnapshot,
    signal: Signal,
) -> dict:
    features = {
        "interval": interval_name,
        "start_time": start.isoformat(sep=" "),
        "end_time": end.isoformat(sep=" "),
        "is_pregame": is_pregame,
        "is_innings_break": is_innings_break,
        "team_a": team_a,
        "team_b": team_b,
        "innings": cricket.innings,
        "batting_team": cricket.batting_team,
        "bowling_team": cricket.bowling_team,
        "innings_runs": cricket.innings_runs,
        "innings_wickets": cricket.innings_wickets,
        "innings_legal_balls": cricket.innings_legal_balls,
        "overs": cricket.overs_str(),
        "run_rate": round(cricket.run_rate, 3),
        "dot_ball_pct": round(cricket.dot_ball_pct, 4),
        "boundary_ball_pct": round(cricket.boundary_ball_pct, 4),
        "boundary_run_share": round(cricket.boundary_run_share, 4),
        "partnership_runs": cricket.partnership_runs,
        "partnership_legal_balls": cricket.partnership_legal_balls,
        "window_runs": window.runs,
        "window_legal_balls": window.legal_balls,
        "window_wickets": window.wickets,
        "window_dot_ball_pct": round(window.dot_ball_pct, 4),
        "decimal_a": market.decimal.get(team_a) if market else None,
        "decimal_b": market.decimal.get(team_b) if market else None,
        "p_raw_a": round(market.p_raw[team_a], 6) if market else None,
        "p_raw_b": round(market.p_raw[team_b], 6) if market else None,
        "p_fair_a": round(market.p_fair[team_a], 6) if market else None,
        "p_fair_b": round(market.p_fair[team_b], 6) if market else None,
        "overround": round(market.overround, 6) if market else None,
        "sent_mean_a": round(sentiment.team_a.mean, 4),
        "sent_mean_b": round(sentiment.team_b.mean, 4),
        "sent_vol_a": sentiment.team_a.volume,
        "sent_vol_b": sentiment.team_b.volume,
        "sent_match_mean": round(sentiment.match_level.mean, 4),
        "sent_match_vol": sentiment.match_level.volume,
        "p_sent_a": None if signal.p_sent_a is None else round(signal.p_sent_a, 6),
        "p_view_a": None if signal.p_view_a is None else round(signal.p_view_a, 6),
        "edge_a": None if signal.edge_a is None else round(signal.edge_a, 6),
        "alpha": round(signal.alpha, 4),
        "signal_reason": signal.reason,
    }
    extra = set(features) - set(LIVE_FEATURE_KEYS)
    if extra:
        raise RuntimeError(f"live_features leaked unexpected keys: {extra}")
    blob = " ".join(str(v).lower() for v in features.values())
    for needle in FORBIDDEN_FEATURE_SUBSTR:
        if needle in features or needle in "".join(features.keys()).lower():
            raise RuntimeError(f"live_features contained forbidden token {needle!r}")
    if "won by" in blob or "forecast" in blob:
        raise RuntimeError("live_features values look like a result leak")
    return features
