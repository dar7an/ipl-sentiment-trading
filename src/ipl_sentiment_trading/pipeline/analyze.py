from __future__ import annotations

from pathlib import Path

from ipl_sentiment_trading.config import TradingParams
from ipl_sentiment_trading.cricket.state import CricketTracker
from ipl_sentiment_trading.data.loaders import LoadedMatch, load_match
from ipl_sentiment_trading.data.timeutil import parse_corpus_datetime
from ipl_sentiment_trading.domain.models import AnalysisResult, IntervalResult
from ipl_sentiment_trading.markets.odds import (
    build_snapshot_timeline,
    latest_snapshot_as_of,
    quote_for_teams,
)
from ipl_sentiment_trading.narrative import build_narrative_provider
from ipl_sentiment_trading.pipeline.features import build_live_features
from ipl_sentiment_trading.sentiment.analyzer import CricketSentimentAnalyzer
from ipl_sentiment_trading.trading.broker import PaperBroker, max_drawdown
from ipl_sentiment_trading.trading.policy import sentiment_to_view


def analyze_match(
    match_ref: str | int | Path,
    *,
    data_root: Path | str | None = None,
    params: TradingParams | None = None,
    narrative: bool = False,
    loaded: LoadedMatch | None = None,
) -> AnalysisResult:
    params = params or TradingParams()
    match = loaded or load_match(match_ref, data_root=data_root)
    snapshots = build_snapshot_timeline(match.odds_timeline)
    tracker = CricketTracker(match.team_a, match.team_b)
    sentimenter = CricketSentimentAnalyzer()
    broker = PaperBroker(params)
    provider = build_narrative_provider(enabled=narrative)

    intervals: list[IntervalResult] = []
    n_chunks = len(match.frozen.chunks)

    for idx, chunk in enumerate(match.frozen.chunks):
        start = parse_corpus_datetime(chunk.start_time)
        end = parse_corpus_datetime(chunk.end_time)
        if start is None or end is None:
            raise ValueError(f"Chunk {chunk.name} missing timestamps")
        tracker.note_interval_flags(is_innings_break=chunk.is_innings_break)
        window = tracker.apply_balls(chunk.balls)
        cricket = tracker.snapshot(
            is_pregame=chunk.is_pregame,
            is_innings_break=chunk.is_innings_break,
        )
        snap = latest_snapshot_as_of(snapshots, end)
        market = quote_for_teams(snap, match.team_a, match.team_b) if snap else None
        sentiment = sentimenter.aggregate_interval(
            chunk.comments,
            match.team_a,
            match.team_b,
            player_team=dict(tracker.player_team),
        )
        signal = sentiment_to_view(sentiment, market, match.team_a, params)
        features = build_live_features(
            interval_name=chunk.name,
            start=start,
            end=end,
            is_pregame=chunk.is_pregame,
            is_innings_break=chunk.is_innings_break,
            team_a=match.team_a,
            team_b=match.team_b,
            cricket=cricket,
            window=window,
            market=market,
            sentiment=sentiment,
            signal=signal,
        )
        mark = broker.mark(market)
        fill = broker.maybe_fill(
            interval_name=chunk.name,
            as_of=end,
            team_a=match.team_a,
            team_b=match.team_b,
            market=market,
            signal_side=signal.side,
            p_view_a=signal.p_view_a,
            reason=signal.reason,
            equity=mark.equity,
        )
        if fill is not None:
            mark = broker.mark(market)

        narrative_text = None
        if provider is not None:
            narrative_text = provider.narrate(features, (match.team_a, match.team_b))

        is_last = idx == n_chunks - 1
        if is_last:
            mark = broker.settle(match.winner)

        intervals.append(
            IntervalResult(
                name=chunk.name,
                start_time=start,
                end_time=end,
                is_pregame=chunk.is_pregame,
                is_innings_break=chunk.is_innings_break,
                cricket=cricket,
                window=window,
                market=market,
                sentiment=sentiment,
                signal=signal,
                fill=fill,
                ledger=mark,
                live_features=features,
                narrative=narrative_text,
            )
        )

    dd, dd_abs = max_drawdown(broker.equity_path)
    hits = sum(1 for f in broker.fills if f.settled_pnl is not None and f.settled_pnl > 0)
    n_fills = len(broker.fills)
    ending = intervals[-1].ledger.equity if intervals else params.starting_bankroll
    return AnalysisResult(
        match_id=match.match_id,
        team_a=match.team_a,
        team_b=match.team_b,
        team_a_abbr=match.team_a_abbr,
        team_b_abbr=match.team_b_abbr,
        date=match.date,
        venue=match.venue,
        round=match.round,
        winner=match.winner,
        winner_note=match.winner_note,
        starting_bankroll=params.starting_bankroll,
        ending_equity=ending,
        realized_pnl=broker.realized_pnl,
        max_drawdown=dd,
        max_drawdown_abs=dd_abs,
        n_fills=n_fills,
        n_hits=hits,
        hit_rate=(hits / n_fills) if n_fills else None,
        narrative_provider=provider.name if provider is not None else "off",
        intervals=intervals,
        fills=broker.fills,
        formula_notes=params.notes,
        missing_xi=match.xi_empty,
    )
