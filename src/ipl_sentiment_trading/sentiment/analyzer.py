from __future__ import annotations

import math
from typing import Iterable

from ipl_sentiment_trading.data.schema import FrozenComment
from ipl_sentiment_trading.domain.models import SentimentBucket, SentimentSnapshot
from ipl_sentiment_trading.sentiment.attribution import attribute_comment
from ipl_sentiment_trading.sentiment.lexicon import CRICKET_LEXICON, normalize_cricket_text

_DELETED = {"", "[deleted]", "[removed]"}
_QUOTE_BANNED = (
    "fuck",
    "dick",
    "shit",
    "cunt",
    "nigger",
    "asshole",
    "porn",
    "suck my",
    "bitch",
    "wtf",
    "stfu",
)


def _publishable_quote(text: str) -> bool:
    compact = " ".join(text.split())
    if len(compact) < 16 or len(compact) > 160:
        return False
    lowered = compact.lower()
    return not any(token in lowered for token in _QUOTE_BANNED)


class CricketSentimentAnalyzer:
    def __init__(self) -> None:
        self._sid = None

    def _ensure(self):
        if self._sid is not None:
            return self._sid
        import nltk
        from nltk.sentiment.vader import SentimentIntensityAnalyzer

        try:
            nltk.data.find("sentiment/vader_lexicon.zip")
        except LookupError:
            nltk.download("vader_lexicon", quiet=True)
        sid = SentimentIntensityAnalyzer()
        sid.lexicon.update(CRICKET_LEXICON)
        self._sid = sid
        return sid

    def score_text(self, text: str) -> float:
        if not isinstance(text, str) or text.strip() in _DELETED:
            return 0.0
        sid = self._ensure()
        normalized = normalize_cricket_text(text)
        return float(sid.polarity_scores(normalized)["compound"])

    def aggregate_interval(
        self,
        comments: Iterable[FrozenComment],
        team_a: str,
        team_b: str,
        player_team: dict[str, str] | None = None,
    ) -> SentimentSnapshot:
        buckets: dict[str, list[tuple[float, int, str]]] = {
            team_a: [],
            team_b: [],
            "match": [],
        }
        total = 0
        for comment in comments:
            text = comment.comment or ""
            if text.strip() in _DELETED:
                continue
            total += 1
            score = self.score_text(text)
            owner = attribute_comment(text, team_a, team_b, player_team)
            buckets[owner].append((score, comment.upvotes, text))

        def summarize(rows: list[tuple[float, int, str]]) -> SentimentBucket:
            if not rows:
                return SentimentBucket()
            scores = [r[0] for r in rows]
            mean = sum(scores) / len(scores)
            weights = [1.0 + math.log1p(max(r[1], 0)) for r in rows]
            wmean = sum(s * w for s, w in zip(scores, weights, strict=True)) / sum(weights)
            ranked = sorted(rows, key=lambda r: r[0])
            neg = [r[2] for r in ranked if r[0] < -0.2 and _publishable_quote(r[2])][:2]
            pos = [r[2] for r in reversed(ranked) if r[0] > 0.2 and _publishable_quote(r[2])][:2]
            return SentimentBucket(
                mean=mean,
                volume=len(rows),
                upvote_weighted_mean=wmean,
            sample_positive=pos,
            sample_negative=neg,
            )

        return SentimentSnapshot(
            team_a=summarize(buckets[team_a]),
            team_b=summarize(buckets[team_b]),
            match_level=summarize(buckets["match"]),
            total_comments=total,
        )
