"""End-to-end pipeline on the real corpus with a scripted fake DecideFn,
plus the lookahead invariant: live features never contain the winner."""

from __future__ import annotations

from ipl_sentiment_trading.corpus.loader import load_match
from ipl_sentiment_trading.jev.types import (
    ChoiceA,
    DecideResult,
    NoulA,
    ScoreA,
    Usage,
)
from ipl_sentiment_trading.pipeline.analyze import analyze_match
from ipl_sentiment_trading.pipeline.features import FORBIDDEN_FEATURE_SUBSTR


def _decide_probabilistic(state, questions):
    answers = {}
    for qid, q in questions.items():
        if q.type == "noul":
            answers[qid] = NoulA(type="noul", noul=0.6)
        elif q.type == "score":
            answers[qid] = ScoreA(type="score", score=3.5, confidence=0.7)
        else:
            keys = list(q.criteria.keys())
            first = keys[0]
            probs = {k: (0.7 if k == first else 0.3 / max(len(keys) - 1, 1)) for k in keys}
            answers[qid] = ChoiceA(type="choice", choice=first, confidence=0.7, probabilities=probs)
    return DecideResult(model="fake", answers=answers, usage=Usage(input_tokens=100))


def test_analyze_match_74_offline_vader():
    res = analyze_match(74, sentiment="vader")
    assert res.match_id == 74
    assert len(res.intervals) == 38
    assert res.sentiment_source == "vader"
    assert res.winner == "Kolkata Knight Riders"
    assert res.ending_equity > 0
    last = res.intervals[-1]
    assert last.ledger.n_open == 0  # everything settled
    assert all(f.settled_pnl is not None for f in res.fills)


def test_analyze_match_74_with_fake_jev():
    res = analyze_match(74, sentiment="jev", decide=_decide_probabilistic)
    assert res.sentiment_source == "jev"
    snaps = [i.sentiment for i in res.intervals if i.sentiment.source == "jev"]
    assert snaps, "jev engine should produce snapshots"
    assert any(s.interval_verdict for s in snaps)


def test_no_lookahead_in_live_features():
    res = analyze_match(74, sentiment="none")
    winner = (res.winner or "").lower()
    for iv in res.intervals:
        for key, value in iv.live_features.items():
            assert not any(t in key.lower() for t in FORBIDDEN_FEATURE_SUBSTR)
            text = str(value).lower()
            assert "forecast" not in text
            assert "won by" not in text
            assert "margin" not in text
    m = load_match(74)
    assert m.summary.winner == "Kolkata Knight Riders"  # frozen, eval only
