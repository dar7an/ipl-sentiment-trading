from __future__ import annotations

import re
from collections import defaultdict

from ipl_sentiment_trading.data.teams import SHORT_ALIASES, TEAM_NICKNAMES, canonicalize_team

_WORD = re.compile(r"[a-z0-9']+")


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def attribute_comment(
    text: str,
    team_a: str,
    team_b: str,
    player_team: dict[str, str] | None = None,
) -> str:
    """Return team_a, team_b, or 'match'."""
    lowered = text.lower()
    tokens = _tokens(text)
    scores: dict[str, int] = defaultdict(int)

    for team in (team_a, team_b):
        canon = canonicalize_team(team) or team
        for nick in TEAM_NICKNAMES.get(canon, ()):
            if " " in nick:
                if nick in lowered:
                    scores[canon] += 2
            elif nick in tokens:
                scores[canon] += 2
        for alias, mapped in SHORT_ALIASES.items():
            if mapped == canon and alias in tokens:
                scores[canon] += 2
        full = canon.lower()
        if full in lowered:
            scores[canon] += 3

    if player_team:
        for name, mapped in player_team.items():
            key = name.lower()
            if not key or mapped not in {team_a, team_b}:
                continue
            if " " in key:
                if key in lowered:
                    scores[mapped] += 2
            elif key in tokens:
                scores[mapped] += 1

    a = scores.get(team_a, 0)
    b = scores.get(team_b, 0)
    if a > b and a > 0:
        return team_a
    if b > a and b > 0:
        return team_b
    return "match"
