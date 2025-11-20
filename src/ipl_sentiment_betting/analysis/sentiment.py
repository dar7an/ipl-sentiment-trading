import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer

class SentimentAnalyzer:
    """
    A class to handle sentiment analysis using NLTK's VADER.
    Ensures the VADER lexicon is downloaded and the analyzer is initialized once.
    """
    
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SentimentAnalyzer, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            try:
                nltk.data.find('sentiment/vader_lexicon.zip')
            except LookupError:
                nltk.download('vader_lexicon')
            
            self.sid = SentimentIntensityAnalyzer()
            self._initialized = True

    def get_sentiment_score(self, comment: str) -> float:
        """
        Calculates the compound sentiment score for a given comment using VADER.

        Args:
            comment: The text comment to analyze.

        Returns:
            The compound sentiment score, a float between -1 and 1.
            Returns 0.0 if the input is not a string.
        """
        if not isinstance(comment, str):
            return 0.0

        return self.sid.polarity_scores(comment)["compound"]
