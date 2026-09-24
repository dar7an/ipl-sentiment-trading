"""Candidate selection: which comments Jev should judge in an interval.

Deterministic pre-filter so the Jev call stays small and informative:
dedupe identical text, keep the highest-upvoted comments, then fill
remaining slots evenly across the window so late moments count too.
"""

from __future__ import annotations

from ipl_sentiment_trading.domain.models import Comment

MAX_TEXT_LEN = 280
_DELETED = {"", "[deleted]", "[removed]"}


def select_candidates(
    comments: list[Comment], k: int = 30
) -> list[tuple[int, Comment]]:
    """Return (original_index, comment) pairs, chronological order."""
    seen: set[str] = set()
    viable: list[tuple[int, Comment]] = []
    for i, c in enumerate(comments):
        text = " ".join(c.text.split())
        if text.strip().lower() in _DELETED:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        viable.append((i, c))

    if len(viable) <= k:
        chosen = viable
    else:
        by_votes = sorted(viable, key=lambda t: t[1].upvotes, reverse=True)[: k // 2]
        taken = {i for i, _ in by_votes}
        rest = [t for t in viable if t[0] not in taken]
        # Even-time fill: pick roughly uniformly spaced survivors.
        need = k - len(by_votes)
        if rest and need > 0:
            step = len(rest) / need
            fill = [rest[int(j * step)] for j in range(need)]
            chosen = sorted(by_votes + fill, key=lambda t: t[0])
        else:
            chosen = by_votes

    out: list[tuple[int, Comment]] = []
    for i, c in chosen:
        text = " ".join(c.text.split())[:MAX_TEXT_LEN]
        out.append((i, Comment(timestamp=c.timestamp, text=text, upvotes=c.upvotes)))
    return out
