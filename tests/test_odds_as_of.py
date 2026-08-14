from __future__ import annotations

from ipl_sentiment_trading.data.schema import FrozenOddsEntry
from ipl_sentiment_trading.data.teams import canonicalize_team
from ipl_sentiment_trading.data.timeutil import parse_corpus_datetime
from ipl_sentiment_trading.markets.odds import (
    build_snapshot_timeline,
    latest_snapshot_as_of,
    quote_for_teams,
)


def test_latest_as_of_t_is_not_first_element() -> None:
    entries = [
        FrozenOddsEntry.model_validate(
            {
                "last_update": "2024-05-26 07:30:00 PM IST",
                "odds": [
                    {"name": "Kolkata Knight Riders", "price": 1.95},
                    {"name": "Sunrisers Hyderabad", "price": 1.87},
                ],
            }
        ),
        FrozenOddsEntry.model_validate(
            {
                "last_update": "2024-05-26 07:40:00 PM IST",
                "odds": [
                    {"name": "Kolkata Knight Riders", "price": 1.50},
                    {"name": "Sunrisers Hyderabad", "price": 2.50},
                ],
            }
        ),
        FrozenOddsEntry.model_validate(
            {
                "last_update": "2024-05-26 07:50:00 PM IST",
                "odds": [
                    {"name": "Kolkata Knight Riders", "price": 1.20},
                    {"name": "Sunrisers Hyderabad", "price": 4.00},
                ],
            }
        ),
    ]
    snaps = build_snapshot_timeline(entries)
    as_of = parse_corpus_datetime("2024-05-26 07:45:00 PM")
    chosen = latest_snapshot_as_of(snaps, as_of)
    assert chosen is not None
    prices = {p.team: p.decimal_odds for p in chosen.prices}
    assert prices["Kolkata Knight Riders"] == 1.50
    assert snaps[0].prices[0].decimal_odds == 1.95


def test_rcb_bangalore_odds_match_bengaluru_team() -> None:
    entry = FrozenOddsEntry.model_validate(
        {
            "last_update": "2024-03-22 07:55:30 PM IST",
            "odds": [
                {"name": "Chennai Super Kings", "price": 1.75},
                {"name": "Royal Challengers Bangalore", "price": 2.1},
            ],
        }
    )
    snap = build_snapshot_timeline([entry])[0]
    quote = quote_for_teams(snap, "Chennai Super Kings", "Royal Challengers Bengaluru")
    assert quote is not None
    assert canonicalize_team("Royal Challengers Bangalore") == "Royal Challengers Bengaluru"
    assert quote.decimal["Royal Challengers Bengaluru"] == 2.1
