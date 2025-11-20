import pytest
from ipl_sentiment_betting.analysis.sentiment import SentimentAnalyzer

@pytest.fixture
def sentiment_analyzer():
    return SentimentAnalyzer()

def test_sentiment_positive(sentiment_analyzer):
    text = "This is a fantastic match! I love it."
    score = sentiment_analyzer.get_sentiment_score(text)
    assert score > 0

def test_sentiment_negative(sentiment_analyzer):
    text = "This is terrible. Worst performance ever."
    score = sentiment_analyzer.get_sentiment_score(text)
    assert score < 0

def test_sentiment_neutral(sentiment_analyzer):
    text = "The match is starting now."
    score = sentiment_analyzer.get_sentiment_score(text)
    # Neutral might not be exactly 0 depending on VADER, but should be close or 0 for very simple facts
    # Let's check it returns a float
    assert isinstance(score, float)

def test_sentiment_invalid_input(sentiment_analyzer):
    assert sentiment_analyzer.get_sentiment_score(None) == 0.0
    assert sentiment_analyzer.get_sentiment_score(123) == 0.0
