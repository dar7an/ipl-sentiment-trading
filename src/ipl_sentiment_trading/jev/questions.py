"""Domain question builders — the Jev surface for this app.

Every fuzzy judgment in the pipeline is declared here as choice/score/noul
questions. Callers build the `state` text; these functions build the questions.
"""

from __future__ import annotations

from ipl_sentiment_trading.domain.models import Comment, TeamRef
from ipl_sentiment_trading.jev.types import ChoiceQ, NoulQ, Question, ScoreQ

_BULL_LEVELS = [
    "firmly expects the favored side to lose; sarcasm or doom about them",
    "leaning pessimistic about the favored side",
    "mixed, hedged, or genuinely neutral read",
    "leaning optimistic about the favored side",
    "firmly expects the favored side to win; celebrating dominance",
]

_REGIMES = {
    "one_sided": "one team clearly dominant; outcome feels nearly decided",
    "tense": "close contest; either side can still win",
    "swing": "momentum actively flipping between sides within this window",
    "dead": "low-stakes passage; drift, dead rubbers, or pre-game idle chat",
}

_SIGNAL_LEVELS = [
    "useless: spam, noise, or almost no on-topic comments",
    "thin: a few on-topic comments, low conviction",
    "some signal but muddy or one-sided spam",
    "decent volume of on-topic opinion, mostly coherent",
    "rich: many on-topic comments with clear conviction about the match",
]


def comments_state(comments: list[Comment], team_a: TeamRef, team_b: TeamRef) -> str:
    """Numbered candidate comments for one interval — the `state` for
    `comment_questions`. Indices must match the candidates' positions."""
    lines = [
        f"Reddit match-thread comments, {team_a.name} ({team_a.abbreviation}) "
        f"vs {team_b.name} ({team_b.abbreviation}), IPL 2024.",
        "Comments are numbered [i] chronologically within a short window:",
    ]
    for i, c in enumerate(comments):
        text = " ".join(c.text.split())
        lines.append(f"[{i}] (+{c.upvotes}) {text}")
    return "\n".join(lines)


def comment_questions(
    comments: list[Comment], team_a: TeamRef, team_b: TeamRef
) -> dict[str, Question]:
    questions: dict[str, Question] = {}
    for i in range(len(comments)):
        questions[f"c{i}_relevant"] = NoulQ(
            instructions=(
                f"Is comment [{i}] about cricket or this match — teams, players, "
                "the game, the crowd, fantasy picks — rather than spam, links, "
                "or unrelated chat?"
            )
        )
        questions[f"c{i}_team"] = ChoiceQ(
            instructions=(
                f"Which side does comment [{i}] support or favor? Favoring a side "
                "means cheering it, praising its players, mocking or dooming the "
                "opponent, or celebrating its wickets/boundaries."
            ),
            criteria={
                "team_a": f"supports {team_a.name} ({team_a.abbreviation})",
                "team_b": f"supports {team_b.name} ({team_b.abbreviation})",
                "neutral": "general commentary, questions, memes, or evenly split",
            },
        )
        questions[f"c{i}_bullish"] = ScoreQ(
            instructions=(
                f"If comment [{i}] favors a side, how bullish is it on that side's "
                "chances right now? Score the middle level for neutral or "
                "off-topic comments."
            ),
            criteria=list(_BULL_LEVELS),
        )
    return questions


def interval_questions(team_a: TeamRef, team_b: TeamRef) -> dict[str, Question]:
    return {
        "regime": ChoiceQ(
            instructions=(
                f"Classify the match regime in this window of "
                f"{team_a.abbreviation} vs {team_b.abbreviation}."
            ),
            criteria=dict(_REGIMES),
        ),
        "signal_quality": ScoreQ(
            instructions=(
                "How informative is this window's comment sample for judging "
                "which side the crowd believes will win?"
            ),
            criteria=list(_SIGNAL_LEVELS),
        ),
        "odds_stale": NoulQ(
            instructions=(
                "Do these odds look stale or erroneous for the cricket state "
                "shown — e.g. unchanged prices through a collapse, implied "
                "probabilities inconsistent with the match situation?"
            )
        ),
        "narrate": NoulQ(
            instructions=(
                "Did anything narratively interesting happen in this window — "
                "a collapse, a comeback, a milestone, a controversial moment — "
                "worth a sentence of prose?"
            )
        ),
    }


def trade_gate_question() -> dict[str, Question]:
    return {
        "gate": NoulQ(
            instructions=(
                "The system wants to place a paper bet on the stated edge. Is "
                "the edge genuine signal — coherent crowd conviction diverging "
                "from the market — rather than noise, a spam burst, or a "
                "data artifact? Answer yes only for a real, defensible edge."
            )
        )
    }


def route_question() -> dict[str, Question]:
    return {
        "drama": ScoreQ(
            instructions=(
                "How dramatic or newsworthy is this match window — the kind of "
                "passage a highlights writer would linger on?"
            ),
            criteria=[
                "routine passage, nothing notable",
                "minor interest only",
                "solid cricket, some talking points",
                "big moment: collapse, milestone, or momentum swing",
                "peak drama: the passage people will remember",
            ],
        )
    }


def compaction_questions(n_facts: int) -> dict[str, Question]:
    """Per stale memory fact i: keep full, trim to a clause, or drop."""
    return {
        f"f{i}": ChoiceQ(
            instructions=(
                f"Is memory item [{i}] still needed for narrating the rest of "
                "the match? keep = load-bearing context; trim = keep one "
                "clause; drop = stale or redundant."
            ),
            criteria={
                "keep": "still load-bearing context",
                "trim": "worth one compressed clause",
                "drop": "stale or redundant",
            },
        )
        for i in range(n_facts)
    }
