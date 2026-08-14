from __future__ import annotations

from ipl_sentiment_trading.config import TradingParams
from ipl_sentiment_trading.narrative.base import features_to_prompt
from ipl_sentiment_trading.pipeline.analyze import analyze_match
from ipl_sentiment_trading.pipeline.features import LIVE_FEATURE_KEYS
from tests.factories import ball, chunk, comment, odds_entry, write_match


def _csk_heavy_match(tmp_path):
    csk_comments = [comment("Thala for a reason, CSK batting is class, yellow army") for _ in range(16)]
    mi_comments = [comment("Mumbai Indians look terrible, MI collapsing") for _ in range(6)]
    comments = csk_comments + mi_comments
    odds = [odds_entry("2024-05-01 07:04:00 PM IST", "Chennai Super Kings", 1.90, "Mumbai Indians", 1.90)]
    chunks = []
    for i in range(3):
        chunks.append(
            chunk(
                f"chunk_{i+1}",
                start=f"2024-05-01 07:{i*5:02d}:00 PM",
                end=f"2024-05-01 07:{i*5+4:02d}:00 PM",
                comments=comments,
                odds=odds,
                balls=[
                    ball(batting="Chennai Super Kings", runs=1, over=float(i) + 0.1),
                    ball(batting="Chennai Super Kings", runs=4, four=True, over=float(i) + 0.2),
                ],
            )
        )
    write_match(
        tmp_path,
        1,
        team_a="Chennai Super Kings",
        team_b="Mumbai Indians",
        chunks=chunks,
        winner_id=6,
        local_id=6,
        visitor_id=2,
    )


def test_live_features_and_prompts_exclude_winner(tmp_path) -> None:
    _csk_heavy_match(tmp_path)
    result = analyze_match(1, data_root=tmp_path, narrative=False)
    assert result.winner == "Mumbai Indians"
    for row in result.intervals:
        keys = set(row.live_features)
        assert keys <= set(LIVE_FEATURE_KEYS)
        joined = " ".join(keys).lower()
        assert "winner" not in joined
        assert "forecast" not in joined
        blob = str(row.live_features).lower()
        assert "won by" not in blob
        assert "forecast_data" not in blob
        assert "winner_team_id" not in blob
        prompt = features_to_prompt(row.live_features, (result.team_a, result.team_b)).lower()
        assert "won by" not in prompt
        assert "winner_team_id" not in prompt
        assert "forecast_data" not in prompt


def test_live_policy_cannot_cheat_with_winner(tmp_path) -> None:
    _csk_heavy_match(tmp_path)
    params = TradingParams(starting_bankroll=1000.0, volume_floor=20, min_team_comments=3, edge_threshold=0.03)
    result = analyze_match(1, data_root=tmp_path, params=params, narrative=False)
    assert result.winner == "Mumbai Indians"
    sides = [f.team for f in result.fills]
    # Cheating (always backing the winner) would be a perfect MI book.
    assert sides, "expected the sentiment view to fire so the test is meaningful"
    assert set(sides) != {"Mumbai Indians"}
    assert "Chennai Super Kings" in sides
    if result.hit_rate is not None:
        assert result.hit_rate < 1.0
