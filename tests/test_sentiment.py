from __future__ import annotations

from ipl_sentiment_trading.sentiment.analyzer import CricketSentimentAnalyzer
from ipl_sentiment_trading.sentiment.attribution import attribute_comment


def test_cricket_lexicon_moves_event_phrases_off_zero() -> None:
    sia = CricketSentimentAnalyzer()
    six = sia.score_text("What a six!")
    duck = sia.score_text("Golden duck")
    maiden = sia.score_text("Wicket maiden")
    assert six != 0.0
    assert duck != 0.0
    assert maiden != 0.0
    assert six > 0
    assert duck < 0
    assert maiden > 0


def test_team_attribution_on_obvious_comments() -> None:
    csk = "Chennai Super Kings"
    mi = "Mumbai Indians"
    assert attribute_comment("Thala for a reason, CSK are winning this", csk, mi) == csk
    assert attribute_comment("Bumrah is unplayable, MI bowling so well", csk, mi) == mi
    assert attribute_comment("What a game this is", csk, mi) == "match"
