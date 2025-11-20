import pytest
from unittest.mock import MagicMock, patch
from ipl_sentiment_betting.core.analyzer import MatchAnalyzer

@pytest.fixture
def mock_genai():
    with patch('ipl_sentiment_betting.core.analyzer.genai') as mock:
        yield mock

@pytest.fixture
def mock_config():
    with patch('ipl_sentiment_betting.core.analyzer.Config') as mock:
        yield mock

@pytest.fixture
def mock_sentiment_analyzer():
    with patch('ipl_sentiment_betting.core.analyzer.SentimentAnalyzer') as mock:
        instance = mock.return_value
        instance.get_sentiment_score.return_value = 0.5
        yield instance

def test_analyzer_initialization(mock_genai, mock_config, mock_sentiment_analyzer):
    analyzer = MatchAnalyzer()
    mock_config.validate.assert_called_once()
    mock_genai.GenerativeModel.assert_called_once()
    # Check if sentiment analyzer was initialized
    assert analyzer.sentiment_analyzer is not None

def test_format_odds_valid(mock_sentiment_analyzer):
    analyzer = MatchAnalyzer()
    odds_data = [{
        "odds": [{"name": "Team A", "price": 1.5}, {"name": "Team B", "price": 2.5}],
        "last_update": "10:00"
    }]
    result = analyzer.format_odds(odds_data)
    assert "Team A: 1.5" in result
    assert "Team B: 2.5" in result
    assert "10:00" in result

def test_summarize_ball_by_ball_metrics(mock_sentiment_analyzer):
    analyzer = MatchAnalyzer()
    balls_data = [
        {
            "ball": "0.1",
            "score": {"runs": 4, "four": True, "ball": True, "name": "Four"},
            "batsman": {"fullname": "Player A"},
            "bowler": {"fullname": "Player B"},
            "name": "Team A"
        },
        {
            "ball": "0.2",
            "score": {"runs": 0, "ball": True, "name": "Dot"},
            "batsman": {"fullname": "Player A"},
            "bowler": {"fullname": "Player B"},
            "name": "Team A"
        }
    ]
    team1_info = {"name": "Team A", "xi": ["Player A"]}
    team2_info = {"name": "Team B", "xi": ["Player B"]}
    
    result = analyzer.summarize_ball_by_ball(balls_data, team1_info, team2_info)
    
    # Check for basic info
    assert "4 runs" in result
    assert "FOUR" in result
    
    # Check for new metrics
    assert "Dot Ball %: 50.0%" in result
    assert "Boundary %: 50.0%" in result
    assert "Partnership Runs" in result

def test_analyze_sentiment(mock_sentiment_analyzer):
    analyzer = MatchAnalyzer()
    comments = [{"comment": "Great shot!"}, {"comment": "Bad luck."}]
    
    # Mock return values for the loop
    analyzer.sentiment_analyzer.get_sentiment_score.side_effect = [0.8, -0.6]
    
    result = analyzer.analyze_sentiment(comments)
    
    assert "Average Score: 0.10" in result["summary"]
    assert "Positive" in result["summary"]
    assert "Negative" in result["summary"]
    assert "Great shot!" in result["top_positive"]
    assert "Bad luck." in result["top_negative"]
