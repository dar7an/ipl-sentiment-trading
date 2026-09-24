"""Fill policy: thesis sizing rules, then the Jev guardrail on every proposal."""

from __future__ import annotations

from ipl_sentiment_trading.config import TradingParams
from ipl_sentiment_trading.domain.models import (
    Fill,
    MarketQuote,
    SentimentSnapshot,
    Signal,
    TradeGate,
)
from ipl_sentiment_trading.jev.questions import trade_gate_question
from ipl_sentiment_trading.jev.types import DecideFn, NoulA
from ipl_sentiment_trading.ledger.book import PaperBook


def kelly_fraction(p_win: float, decimal_odds: float) -> float:
    if decimal_odds <= 1.0 or not 0.0 < p_win < 1.0:
        return 0.0
    b = decimal_odds - 1.0
    return max(0.0, (p_win * decimal_odds - 1.0) / b)


def gate_state(
    *,
    interval_name: str,
    team: str,
    signal: Signal,
    quote: MarketQuote,
    sentiment: SentimentSnapshot,
    stake: float,
    equity: float,
) -> str:
    edge = signal.edge_a or 0.0
    p_win = signal.p_view_a if edge > 0 else (1.0 - (signal.p_view_a or 0.0))
    verdict = sentiment.interval_verdict
    regime = verdict.regime if verdict else "unknown"
    quality = verdict.signal_quality if verdict else 0.0
    eff_vol = sentiment.team_a.effective_volume + sentiment.team_b.effective_volume
    return (
        f"Paper-trading proposal for interval '{interval_name}'.\n"
        f"Proposed: back {team} at decimal {quote.decimal.get(team)} "
        f"(de-vigged market prob {quote.p_fair.get(team):.3f}, "
        f"sentiment-adjusted view prob {p_win:.3f}, edge {abs(edge):.1%}).\n"
        f"Effective crowd volume {eff_vol:.0f} (alpha={signal.alpha:.2f}); "
        f"regime={regime}, signal_quality={quality:.2f}.\n"
        f"Stake {stake:.2f} on equity {equity:.2f}."
    )


def propose_fill(
    *,
    interval_name: str,
    as_of,
    signal: Signal,
    quote: MarketQuote | None,
    sentiment: SentimentSnapshot,
    book: PaperBook,
    params: TradingParams,
    gate: DecideFn | None = None,
) -> Fill | None:
    """Thesis sizing, then — when a DecideFn is provided — the Jev guardrail."""
    if signal.reason != "ok" or signal.side is None or quote is None:
        return None
    if signal.p_view_a is None or signal.edge_a is None:
        return None
    team = signal.side
    if book.has_open_on(team):
        return None
    cap = params.max_exposure_frac * params.starting_bankroll
    room = cap - book.exposure
    if room < params.min_stake:
        return None
    decimal = quote.decimal.get(team)
    if decimal is None or decimal <= 1.0:
        return None
    p_win = signal.p_view_a if signal.edge_a > 0 else 1.0 - signal.p_view_a
    f_star = kelly_fraction(p_win, decimal)
    if f_star <= 0:
        return None
    equity = book.cash + book.exposure
    stake = min(
        params.kelly_fraction * f_star * equity,
        params.max_stake_frac * equity,
        book.cash,
        room,
    )
    stake = round(stake, 4)
    if stake < params.min_stake:
        return None

    gate_result: TradeGate | None = None
    if gate is not None:
        state = gate_state(
            interval_name=interval_name, team=team, signal=signal,
            quote=quote, sentiment=sentiment, stake=stake, equity=equity,
        )
        res = gate(state, trade_gate_question())
        ans = res.answers.get("gate")
        if isinstance(ans, NoulA):
            gate_result = TradeGate(
                approved=ans.noul >= 0.5,
                p_genuine=ans.noul,
            )
            if not gate_result.approved:
                return None
        else:
            gate_result = TradeGate(approved=True, skipped=True)

    return book.record_fill(
        Fill(
            interval_name=interval_name,
            as_of=as_of,
            team=team,
            decimal_odds=decimal,
            stake=stake,
            kelly_raw=f_star,
            reason=signal.reason,
            gate=gate_result,
        )
    )

