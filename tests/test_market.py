from __future__ import annotations

from datetime import datetime

from ipl_sentiment_trading.corpus.loader import load_match
from ipl_sentiment_trading.domain.models import OddsSnapshot, Price
from ipl_sentiment_trading.market.odds import (
    implied_probability,
    latest_snapshot_as_of,
    quote_as_of,
    quote_for_teams,
)


def _snap(minute, a, b, idx=0):
    return OddsSnapshot(
        last_update=datetime(2024, 5, 26, 19, minute, 0),
        prices=[Price(team="A", decimal_odds=a), Price(team="B", decimal_odds=b)],
        source_index=idx,
    )


def test_implied_and_devig():
    assert implied_probability(2.0) == 0.5
    q = quote_for_teams(_snap(0, 2.0, 2.0), "A", "B")
    assert q.p_fair == {"A": 0.5, "B": 0.5}
    q2 = quote_for_teams(_snap(0, 1.9, 1.9), "A", "B")
    assert q2.overround > 0
    assert abs(sum(q2.p_fair.values()) - 1.0) < 1e-9
    assert implied_probability(1.01) != 1.0


def test_as_of_selects_last_prior_snapshot():
    snaps = [_snap(10, 2.0, 2.0, 0), _snap(20, 1.8, 2.2, 1), _snap(30, 1.5, 3.0, 2)]
    assert latest_snapshot_as_of(snaps, datetime(2024, 5, 26, 19, 25, 0)).source_index == 1
    assert latest_snapshot_as_of(snaps, datetime(2024, 5, 26, 19, 5, 0)) is None


def test_carry_forward_flag():
    snaps = [_snap(10, 2.0, 2.0, 0)]
    q1 = quote_as_of(snaps, datetime(2024, 5, 26, 19, 15, 0), "A", "B")
    assert q1 and not q1.is_carry_forward
    q2 = quote_as_of(snaps, datetime(2024, 5, 26, 19, 25, 0), "A", "B", prev_snapshot=snaps[0])
    assert q2 and q2.is_carry_forward


def test_match_74_odds_real():
    m = load_match(74)
    a, b = m.summary.team_a.name, m.summary.team_b.name
    q = quote_for_teams(m.odds[-1], a, b)
    assert q is not None
    assert q.overround > 0
    assert abs(sum(q.p_fair.values()) - 1.0) < 1e-9
    assert all(v > 0 for v in q.p_fair.values())
