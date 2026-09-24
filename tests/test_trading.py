from __future__ import annotations

from datetime import datetime

from ipl_sentiment_trading.config import TradingParams
from ipl_sentiment_trading.domain.models import (
    Fill,
    MarketQuote,
    SentimentBucket,
    SentimentSnapshot,
    Signal,
)
from ipl_sentiment_trading.jev.types import DecideResult, NoulA, Usage
from ipl_sentiment_trading.ledger.book import PaperBook, max_drawdown
from ipl_sentiment_trading.policy.decide import kelly_fraction, propose_fill
from ipl_sentiment_trading.signal.view import compute_view, logit, sigmoid

P = TradingParams()
TEAM_A, TEAM_B = "Sunrisers Hyderabad", "Kolkata Knight Riders"


def _quote(p_a=0.6):
    return MarketQuote(
        as_of=datetime(2024, 5, 26, 20, 10),
        decimal={TEAM_A: 1.0 / p_a, TEAM_B: 1.0 / (1 - p_a)},
        p_raw={TEAM_A: p_a, TEAM_B: 1 - p_a},
        overround=0.0,
        p_fair={TEAM_A: p_a, TEAM_B: 1 - p_a},
    )


def _sentiment(mean_a, mean_b, vol_a=15, vol_b=15, eff_a=None, eff_b=None):
    return SentimentSnapshot(
        team_a=SentimentBucket(mean=mean_a, volume=vol_a, effective_volume=eff_a or float(vol_a)),
        team_b=SentimentBucket(mean=mean_b, volume=vol_b, effective_volume=eff_b or float(vol_b)),
        source="jev",
    )


def _signal_ok(side=TEAM_A, p_view_a=0.7):
    return Signal(
        p_market_a=0.6, p_sent_a=0.75, p_view_a=p_view_a,
        edge_a=p_view_a - 0.6, alpha=0.5, side=side, reason="ok",
    )


def test_view_math_matches_thesis():
    q = _quote(0.6)
    snap = _sentiment(0.6, -0.4)
    sig = compute_view(q, snap, TEAM_A, TEAM_B, P)
    assert sig.reason == "ok" and sig.side == TEAM_A
    n_eff = 30.0
    alpha = n_eff / (n_eff + 40)
    import math

    expected = sigmoid(logit(0.6) + alpha * 1.5 * math.tanh(0.6 - (-0.4)))
    assert abs(sig.p_view_a - expected) < 1e-9
    assert sig.alpha == alpha
    assert sig.edge_a > 0.03


def test_view_gates():
    q = _quote(0.6)
    assert compute_view(None, _sentiment(0.5, 0.0), TEAM_A, TEAM_B, P).reason == "no-odds"
    assert compute_view(q, _sentiment(0.5, 0.0, vol_a=2), TEAM_A, TEAM_B, P).reason == "low-volume"
    assert compute_view(q, _sentiment(0.5, 0.0, vol_a=3, vol_b=2), TEAM_A, TEAM_B, P).reason == "low-volume"
    assert compute_view(q, _sentiment(0.1, 0.05), TEAM_A, TEAM_B, P).reason == "edge-below-threshold"


def test_kelly_and_fill():
    assert kelly_fraction(0.7, 1.0 / 0.6) > 0
    assert kelly_fraction(0.4, 1.0 / 0.6) == 0.0
    book = PaperBook(P)
    snap = _sentiment(0.6, -0.4)
    fill = propose_fill(
        interval_name="t", as_of=datetime(2024, 5, 26, 20, 10),
        signal=_signal_ok(), quote=_quote(), sentiment=snap, book=book, params=P,
    )
    assert fill is not None and fill.team == TEAM_A
    assert fill.stake <= P.max_stake_frac * 1000 + 1e-6
    assert book.cash == P.starting_bankroll - fill.stake
    # No same-side pyramid
    assert propose_fill(
        interval_name="t2", as_of=datetime(2024, 5, 26, 20, 15),
        signal=_signal_ok(), quote=_quote(), sentiment=snap, book=book, params=P,
    ) is None


def test_gate_can_veto():
    def veto(state, questions):
        return DecideResult(model="fake", answers={"gate": NoulA(type="noul", noul=0.1)}, usage=Usage())

    book = PaperBook(P)
    fill = propose_fill(
        interval_name="t", as_of=datetime(2024, 5, 26, 20, 10),
        signal=_signal_ok(), quote=_quote(), sentiment=_sentiment(0.6, -0.4),
        book=book, params=P, gate=veto,
    )
    assert fill is None
    assert book.exposure == 0

    def approve(state, questions):
        return DecideResult(model="fake", answers={"gate": NoulA(type="noul", noul=0.9)}, usage=Usage())

    fill = propose_fill(
        interval_name="t", as_of=datetime(2024, 5, 26, 20, 10),
        signal=_signal_ok(), quote=_quote(), sentiment=_sentiment(0.6, -0.4),
        book=book, params=P, gate=approve,
    )
    assert fill is not None and fill.gate.approved and fill.gate.p_genuine == 0.9


def test_book_marks_and_settles():
    book = PaperBook(P)
    book.record_fill(Fill(
        interval_name="t", as_of=datetime(2024, 5, 26, 20, 10),
        team=TEAM_A, decimal_odds=2.0, stake=40.0, kelly_raw=0.5, reason="ok",
    ))
    snap = book.mark(_quote(0.7))
    assert abs(snap.identity_cash_plus_exposure - P.starting_bankroll) < 1e-9
    assert snap.open_mtm_pnl == 40 * 0.7 * 2.0 - 40
    snap = book.settle(TEAM_A)
    assert snap.n_open == 0
    assert snap.realized_pnl == 40.0  # 40*(2.0-1)
    assert abs(snap.equity - (P.starting_bankroll + 40.0)) < 1e-9


def test_max_drawdown():
    dd, abs_dd = max_drawdown([100, 120, 90, 95])
    assert dd == (120 - 90) / 120
    assert abs_dd == 30
