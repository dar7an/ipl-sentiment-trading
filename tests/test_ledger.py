from __future__ import annotations

from ipl_sentiment_trading.config import TradingParams
from ipl_sentiment_trading.pipeline.analyze import analyze_match
from tests.factories import ball, chunk, comment, odds_entry, write_match


def test_ledger_identity_on_fixture(tmp_path) -> None:
    comments = [comment("Thala for a reason, CSK class batting") for _ in range(16)] + [
        comment("Mumbai Indians look awful tonight, MI bowling leaking") for _ in range(6)
    ]
    chunks = [
        chunk(
            "chunk_1",
            start="2024-05-01 07:00:00 PM",
            end="2024-05-01 07:05:00 PM",
            comments=comments,
            odds=[odds_entry("2024-05-01 07:04:00 PM IST", "Chennai Super Kings", 2.10, "Mumbai Indians", 1.75)],
            balls=[ball(batting="Chennai Super Kings", runs=4, four=True)],
        ),
        chunk(
            "chunk_2",
            start="2024-05-01 07:05:00 PM",
            end="2024-05-01 07:10:00 PM",
            comments=comments,
            odds=[odds_entry("2024-05-01 07:09:00 PM IST", "Chennai Super Kings", 1.80, "Mumbai Indians", 2.05)],
            balls=[ball(batting="Chennai Super Kings", runs=6, six=True, over=0.2)],
        ),
    ]
    write_match(
        tmp_path,
        2,
        team_a="Chennai Super Kings",
        team_b="Mumbai Indians",
        chunks=chunks,
        winner_id=2,
        local_id=2,
        visitor_id=6,
    )
    params = TradingParams(starting_bankroll=1000.0)
    result = analyze_match(2, data_root=tmp_path, params=params, narrative=False)
    last = result.intervals[-1].ledger
    assert last.n_open == 0
    assert last.cash + last.exposure == last.identity_cash_plus_exposure
    assert last.equity == last.cash
    assert result.starting_bankroll + result.realized_pnl == result.ending_equity
    assert abs(last.identity_cash_plus_exposure - (params.starting_bankroll + result.realized_pnl)) < 1e-6
    for row in result.intervals[:-1]:
        led = row.ledger
        assert abs(led.cash + led.exposure - (params.starting_bankroll + led.realized_pnl)) < 1e-6
