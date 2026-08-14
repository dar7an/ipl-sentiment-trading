from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class NarrativeProvider(Protocol):
    name: str

    def narrate(self, live_features: dict, teams: tuple[str, str]) -> str: ...


class NullNarrative:
    name = "off"

    def narrate(self, live_features: dict, teams: tuple[str, str]) -> str:
        return ""


def features_to_prompt(live_features: dict, teams: tuple[str, str]) -> str:
    team_a, team_b = teams
    lines = [
        "You are annotating a paper-trading research interval. Use only the as-of-t numbers.",
        "Do not guess a winner. Do not claim the match is over. Do not invent odds or scores.",
        "Never write 'implied odds' for a decimal price. Decimal odds and probabilities are different.",
        f"Teams: {team_a} vs {team_b}",
        "As-of-t features:",
    ]
    for key in sorted(live_features):
        lines.append(f"  {key}: {live_features[key]}")
    lines.append(
        "Write 3-5 sentences: cricket state, de-vigged market vs sentiment view, and whether "
        "the paper rule would bet. Neutral tone."
    )
    return "\n".join(lines)
