from __future__ import annotations

import pytest

from ipl_sentiment_trading.data.loaders import load_match
from ipl_sentiment_trading.data.schema import MatchLoadError, parse_match_file


def test_loader_accepts_real_match_74() -> None:
    match = load_match(74)
    assert match.match_id == 74
    assert match.team_a == "Sunrisers Hyderabad"
    assert match.team_b == "Kolkata Knight Riders"
    assert match.xi_empty is True
    assert match.frozen.chunks
    assert match.frozen.chunks[0].name == "chunk_1"
    assert match.winner == "Kolkata Knight Riders"
    assert match.venue is not None


def test_loader_rejects_nonsense() -> None:
    with pytest.raises(MatchLoadError):
        parse_match_file({"hello": "world", "chunks": "nope"})
    with pytest.raises(MatchLoadError):
        parse_match_file([])
    with pytest.raises(MatchLoadError):
        parse_match_file({"match_info": {"team1": {"name": "A"}, "team2": {"name": "B"}}, "chunks": []})
