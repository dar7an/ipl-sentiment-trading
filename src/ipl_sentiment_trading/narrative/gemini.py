from __future__ import annotations

from ipl_sentiment_trading.narrative.base import features_to_prompt


class GeminiNarrative:
    name = "gemini"

    def __init__(self, api_key: str, model: str) -> None:
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self._model = model

    def narrate(self, live_features: dict, teams: tuple[str, str]) -> str:
        prompt = features_to_prompt(live_features, teams)
        response = self._client.models.generate_content(model=self._model, contents=prompt)
        text = getattr(response, "text", None)
        return (text or "").strip()
