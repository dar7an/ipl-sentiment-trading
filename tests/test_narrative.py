from __future__ import annotations

import sys

from ipl_sentiment_trading.narrative import build_narrative_provider
from ipl_sentiment_trading.pipeline.analyze import analyze_match
from tests.factories import ball, chunk, comment, odds_entry, write_match


def test_build_provider_offline_is_none_and_skips_google(monkeypatch) -> None:
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("NARRATIVE_BASE_URL", raising=False)
    sys.modules.pop("google.genai", None)
    sys.modules.pop("google", None)
    assert build_narrative_provider(enabled=False) is None
    assert "google.genai" not in sys.modules
    assert build_narrative_provider(enabled=True) is None
    assert "google.genai" not in sys.modules


def test_analyze_offline_does_not_construct_narrative(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("NARRATIVE_BASE_URL", raising=False)
    write_match(
        tmp_path,
        4,
        team_a="Chennai Super Kings",
        team_b="Mumbai Indians",
        chunks=[
            chunk(
                "chunk_1",
                start="2024-05-01 07:00:00 PM",
                end="2024-05-01 07:05:00 PM",
                comments=[comment("hello")],
                odds=[odds_entry("2024-05-01 07:04:00 PM IST", "Chennai Super Kings", 1.90, "Mumbai Indians", 1.90)],
                balls=[ball(batting="Chennai Super Kings", runs=0)],
            )
        ],
        winner_id=2,
        local_id=2,
        visitor_id=6,
    )
    sys.modules.pop("google.genai", None)
    result = analyze_match(4, data_root=tmp_path, narrative=False)
    assert result.narrative_provider == "off"
    assert all(row.narrative is None for row in result.intervals)
    assert "google.genai" not in sys.modules
    assert "ipl_sentiment_trading.narrative.gemini" not in sys.modules
