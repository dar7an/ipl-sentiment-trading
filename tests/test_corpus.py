from __future__ import annotations

import pytest

from ipl_sentiment_trading.corpus.loader import (
    CORPUS_GAPS,
    MissingMatchError,
    available_match_ids,
    load_match,
)
from ipl_sentiment_trading.corpus.teams import (
    abbreviation,
    canonicalize_team,
    team_ref,
    winner_from_id,
)


def test_canonicalize_bengaluru_variants():
    assert canonicalize_team("Royal Challengers Bangalore") == "Royal Challengers Bengaluru"
    assert canonicalize_team("Royal Challengers Bengaluru") == "Royal Challengers Bengaluru"
    assert canonicalize_team("rcb") == "Royal Challengers Bengaluru"
    assert abbreviation("Royal Challengers Bangalore") == "RCB"
    assert abbreviation("kkr") == "KKR"


def test_team_ref_and_winner():
    ref = team_ref("sunrisers hyderabad")
    assert ref.abbreviation == "SRH"
    assert ref.sportmonks_id == 9
    assert winner_from_id(9, ("X", "Y")) == "Sunrisers Hyderabad"


def test_match_ids_and_gaps():
    ids = available_match_ids()
    assert 74 in ids
    for gap in CORPUS_GAPS:
        assert gap not in ids
        with pytest.raises(MissingMatchError):
            load_match(gap)


def test_load_match_74():
    m = load_match(74)
    s = m.summary
    assert s.match_id == 74
    assert s.team_a.abbreviation in {"SRH", "KKR"}
    assert s.team_b.abbreviation in {"SRH", "KKR"}
    assert s.team_a.name != s.team_b.name
    assert s.winner == "Kolkata Knight Riders"
    assert s.missing_xi is True
    assert len(m.intervals) == 38
    first = m.intervals[0]
    assert first.is_pregame
    assert first.comments
    assert first.end_time > first.start_time
    assert m.odds, "odds timeline should be non-empty"
    last = m.odds[-1]
    assert {p.team for p in last.prices} == {s.team_a.name, s.team_b.name}
    assert m.balls, "balls file should load"


def test_load_match_by_path():
    from pathlib import Path

    m = load_match(Path("data/chunks/74.json"))
    assert m.summary.match_id == 74


def test_no_forecast_leak():
    m = load_match(74)
    for ball in m.balls:
        assert not hasattr(ball, "forecast_data")
        assert "forecast_data" not in (ball.model_dump() or {})
