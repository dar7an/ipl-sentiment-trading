"""Gemma 4 narrator — Jev decides *whether* and *which model* narrates.

Jev's `narrate` noul (from the interval decision batch) gates prose at
all; `route_question` scores window drama and routes between
gemma-4-26b-a4b-it (routine) and gemma-4-31b-it (big moments). Memory is
a list of match facts that Jev compacts (keep/trim/drop) as it grows —
generation itself is the only thing Gemma 4 does.
"""

from __future__ import annotations

import os
from typing import Any

from ipl_sentiment_trading.domain.models import (
    Interval,
    MatchSummary,
    NarratorRoute,
    SentimentSnapshot,
    TeamRef,
)
from ipl_sentiment_trading.jev.questions import compaction_questions, route_question
from ipl_sentiment_trading.jev.types import ChoiceA, DecideFn, ScoreA

DEFAULT_MODEL = "gemma-4-26b-a4b-it"
PRO_MODEL = "gemma-4-31b-it"
_PRO_DRAMA_CUT = 4.0
_MAX_FACTS = 8


def _gemini_key() -> str | None:
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")


def _genai_client():
    try:
        from google import genai
    except ImportError:
        return None
    key = _gemini_key()
    if not key:
        return None
    return genai.Client(api_key=key)


class GemmaNarrator:
    def __init__(
        self,
        *,
        decide: DecideFn | None,
        team_a: TeamRef,
        team_b: TeamRef,
        match: MatchSummary | None = None,
        fast_model: str | None = None,
        pro_model: str | None = None,
        client: Any = None,
    ) -> None:
        self.decide = decide
        self.team_a = team_a
        self.team_b = team_b
        self.match = match
        self.fast_model = fast_model or os.getenv("NARRATIVE_MODEL", DEFAULT_MODEL)
        self.pro_model = pro_model or os.getenv("NARRATIVE_MODEL_PRO", PRO_MODEL)
        self._client = client if client is not None else _genai_client()
        self.memory: list[str] = []
        self.routes: list[NarratorRoute] = []

    @property
    def provider_name(self) -> str:
        if self._client is None:
            return "off"
        used = {r.model for r in self.routes}
        if len(used) == 1:
            return used.pop()
        return "gemma-4 (routed)" if used else f"{self.fast_model} (idle)"

    def route(self, features: dict) -> NarratorRoute:
        """Jev scores drama 1..5; >=4 routes to the 31B narrator."""
        if self.decide is None:
            return NarratorRoute(model=self.fast_model, reason="no-decide")
        state = (
            f"Match window in {self.team_a.abbreviation} vs "
            f"{self.team_b.abbreviation}: "
            f"innings {features.get('innings')}, score "
            f"{features.get('innings_runs')}/{features.get('innings_wickets')}, "
            f"window runs {features.get('window_runs')} off "
            f"{features.get('window_legal_balls')} balls, "
            f"{features.get('window_wickets')} wickets, "
            f"regime {features.get('regime')}, market p* "
            f"{features.get('p_fair_a')}."
        )
        res = self.decide(state, route_question())
        ans = res.answers.get("drama")
        score = ans.score if isinstance(ans, ScoreA) else 3.0
        model = self.pro_model if score >= _PRO_DRAMA_CUT else self.fast_model
        route = NarratorRoute(
            model=model,
            drama_score=score,
            reason="big-moment" if model == self.pro_model else "routine",
        )
        self.routes.append(route)
        return route

    def _compact_memory(self) -> None:
        """Jev prunes stale memory facts so the prompt stays small."""
        if self.decide is None or len(self.memory) <= _MAX_FACTS:
            return
        state = (
            "Running memory for narrating an IPL match. Items:\n"
            + "\n".join(f"[{i}] {f}" for i, f in enumerate(self.memory))
        )
        res = self.decide(state, compaction_questions(len(self.memory)))
        kept: list[str] = []
        for i, fact in enumerate(self.memory):
            ans = res.answers.get(f"f{i}")
            choice = ans.choice if isinstance(ans, ChoiceA) else "keep"
            if choice == "keep":
                kept.append(fact)
            elif choice == "trim":
                kept.append(fact.split(";")[0].split(",")[0])
        self.memory = kept[-_MAX_FACTS:]

    def _prompt(self, features: dict, sent: SentimentSnapshot) -> str:
        a, b = self.team_a.abbreviation, self.team_b.abbreviation
        quotes = (sent.team_a.sample_positive + sent.team_b.sample_positive)[:3]
        memory = "\n".join(f"- {m}" for m in self.memory) or "- match beginning"
        return (
            f"You are a terse cricket commentator writing one sentence of prose "
            f"for a paper-trading book's match journal.\n"
            f"Match: {a} vs {b}, IPL 2024.\n"
            f"Window facts: innings {features.get('innings')}, "
            f"{features.get('batting_team')} {features.get('innings_runs')}/"
            f"{features.get('innings_wickets')} in {features.get('overs')} ov, "
            f"RR {features.get('run_rate')}; window {features.get('window_runs')} runs, "
            f"{features.get('window_wickets')} wickets; regime {features.get('regime')}; "
            f"crowd lean {a} {features.get('sent_mean_a')}, {b} {features.get('sent_mean_b')}; "
            f"market {features.get('p_fair_a')}.\n"
            f"Memory so far:\n{memory}\n"
            + (f"Fan voices: {quotes}\n" if quotes else "")
            + "Write exactly one sentence, present tense, no emojis, no odds talk."
        )

    def narrate(
        self, interval: Interval, features: dict, sent: SentimentSnapshot
    ) -> str | None:
        if self._client is None:
            return None
        self._compact_memory()
        route = self.route(features)
        prompt = self._prompt(features, sent)
        try:
            resp = self._client.models.generate_content(
                model=route.model, contents=prompt
            )
            text = (resp.text or "").strip()
        except Exception:
            return None
        if text:
            fact = f"{features.get('overs')} ov inn{features.get('innings')}: {text}"
            self.memory.append(fact)
            self._compact_memory()
        return text or None
