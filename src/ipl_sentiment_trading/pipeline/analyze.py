"""analyze_match — the pipeline: corpus → cricket/market/sentiment → view → book.

Cumulative cricket state is fed from the complete balls feed filtered to
each interval's window — never from chunk-embedded subsets, never from
forecast data. The match winner is read exactly once, at settle time.
"""

from __future__ import annotations

from pathlib import Path

from ipl_sentiment_trading.config import TradingParams
from ipl_sentiment_trading.corpus.loader import CorpusPaths, load_match
from ipl_sentiment_trading.cricket.state import CricketTracker
from ipl_sentiment_trading.domain.models import (
    AnalysisResult,
    CorpusMatch,
    IntervalResult,
    SentimentSnapshot,
)
from ipl_sentiment_trading.jev.types import DecideFn
from ipl_sentiment_trading.ledger.book import PaperBook, max_drawdown
from ipl_sentiment_trading.market.odds import latest_snapshot_as_of, quote_as_of
from ipl_sentiment_trading.pipeline.features import build_live_features
from ipl_sentiment_trading.policy.decide import propose_fill
from ipl_sentiment_trading.signal.view import compute_view


def _resolve_decide(decide: DecideFn | None):
    """Return (decide_fn, usage_dict_or_None). Auto-builds a client only when
    API keys are actually present — otherwise the pipeline stays offline."""
    if decide is not None:
        return decide, getattr(decide, "tracer", None)
    import os

    if not (os.getenv("TYPESAFE_API_KEY") or os.getenv("JEV_API_KEY")):
        return None, None
    from ipl_sentiment_trading.jev.client import DecideClient

    client = DecideClient()
    return client.decide, getattr(client, "tracer", None)


def _build_sentiment_engine(sentiment: str, decide, team_a, team_b, sample_k):
    if sentiment == "none":
        return "none", None
    if sentiment == "vader" or (sentiment == "auto" and decide is None):
        from ipl_sentiment_trading.sentiment.vader import VaderSentimentAnalyzer

        return "vader", VaderSentimentAnalyzer()
    from ipl_sentiment_trading.sentiment.jev_engine import JevSentimentEngine

    return "jev", JevSentimentEngine(decide, team_a, team_b, max_candidates=sample_k)


def analyze_match(
    match: int | str | Path | CorpusMatch,
    *,
    data_root: Path | str | None = None,
    params: TradingParams | None = None,
    sentiment: str = "auto",
    narrate: bool = False,
    sample_k: int = 30,
    decide: DecideFn | None = None,
) -> AnalysisResult:
    params = params or TradingParams()
    m: CorpusMatch = (
        match
        if isinstance(match, CorpusMatch)
        else load_match(match, root=CorpusPaths(data_root) if data_root else None)
    )
    team_a, team_b = m.summary.team_a, m.summary.team_b

    decide_fn, tracer = _resolve_decide(decide)
    engine_kind, engine = _build_sentiment_engine(
        sentiment, decide_fn, team_a, team_b, sample_k
    )
    book = PaperBook(params)
    tracker = CricketTracker(team_a.name, team_b.name)
    narrator = None
    if narrate:
        from ipl_sentiment_trading.narrate.gemma import GemmaNarrator

        narrator = GemmaNarrator(
            decide=decide_fn,
            team_a=team_a,
            team_b=team_b,
            match=m.summary,
        )

    # Complete ball feed ordered for windowed consumption.
    balls = sorted(
        m.balls, key=lambda b: (b.updated_at is None, b.updated_at or b.ball, b.ball)
    )
    cursor = 0
    prev_snap = None
    intervals: list[IntervalResult] = []
    n_iv = len(m.intervals)

    for idx, iv in enumerate(m.intervals):
        end = iv.end_time
        tracker.note_interval_flags(is_innings_break=iv.is_innings_break)
        feed: list = []
        while cursor < len(balls):
            u = balls[cursor].updated_at
            if u is not None and u > end:
                break
            feed.append(balls[cursor])
            cursor += 1
        window = tracker.apply_balls(feed)
        cricket = tracker.snapshot(
            is_pregame=iv.is_pregame, is_innings_break=iv.is_innings_break
        )
        quote = quote_as_of(
            m.odds, end, team_a.name, team_b.name, prev_snapshot=prev_snap
        )
        snap = latest_snapshot_as_of(m.odds, end)
        if snap is not None:
            prev_snap = snap

        if engine_kind == "jev":
            sent = engine.analyze(iv, cricket, quote)
        elif engine_kind == "vader":
            sent = engine.aggregate_interval(
                iv.comments, team_a.name, team_b.name,
                player_team=dict(tracker.player_team),
            )
            sent.source = "vader"
        else:
            sent = SentimentSnapshot(total_comments=len(iv.comments), source="none")

        signal = compute_view(quote, sent, team_a.name, team_b.name, params)
        features = build_live_features(
            interval_name=iv.name,
            start=iv.start_time,
            end=end,
            is_pregame=iv.is_pregame,
            is_innings_break=iv.is_innings_break,
            team_a=team_a.name,
            team_b=team_b.name,
            cricket=cricket,
            window=window,
            market=quote,
            sentiment=sent,
            signal=signal,
        )
        mark = book.mark(quote)
        fill = propose_fill(
            interval_name=iv.name,
            as_of=end,
            signal=signal,
            quote=quote,
            sentiment=sent,
            book=book,
            params=params,
            gate=decide_fn,
        )
        if fill is not None:
            mark = book.mark(quote)

        narrative_text = None
        verdict = sent.interval_verdict
        if narrator is not None and verdict is not None and verdict.narrate >= 0.5:
            narrative_text = narrator.narrate(iv, features, sent)

        if idx == n_iv - 1:
            mark = book.settle(m.summary.winner)

        intervals.append(
            IntervalResult(
                name=iv.name,
                start_time=iv.start_time,
                end_time=end,
                is_pregame=iv.is_pregame,
                is_innings_break=iv.is_innings_break,
                cricket=cricket,
                window=window,
                market=quote,
                sentiment=sent,
                signal=signal,
                fill=fill,
                ledger=mark,
                live_features=features,
                narrative=narrative_text,
            )
        )

    dd, dd_abs = max_drawdown(book.equity_path)
    hits = sum(1 for f in book.fills if (f.settled_pnl or 0) > 0)
    ending = intervals[-1].ledger.equity if intervals else params.starting_bankroll
    usage = {}
    if tracer is not None:
        usage = tracer.totals()
    return AnalysisResult(
        match_id=m.summary.match_id,
        team_a=team_a.name,
        team_b=team_b.name,
        team_a_abbr=team_a.abbreviation,
        team_b_abbr=team_b.abbreviation,
        date=m.summary.date,
        venue=m.summary.venue,
        round=m.summary.round,
        winner=m.summary.winner,
        winner_note=m.summary.winner_note,
        starting_bankroll=params.starting_bankroll,
        ending_equity=ending,
        realized_pnl=book.realized_pnl,
        max_drawdown=dd,
        max_drawdown_abs=dd_abs,
        n_fills=len(book.fills),
        n_hits=hits,
        hit_rate=(hits / len(book.fills)) if book.fills else None,
        narrative_provider=(narrator.provider_name if narrator else "off"),
        intervals=intervals,
        fills=book.fills,
        formula_notes=params.notes,
        missing_xi=m.summary.missing_xi,
        jev_usage=usage,
        sentiment_source=engine_kind,
    )
