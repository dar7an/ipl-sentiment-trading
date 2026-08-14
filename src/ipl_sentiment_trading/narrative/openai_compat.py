from __future__ import annotations

import httpx

from ipl_sentiment_trading.narrative.base import features_to_prompt


class OpenAICompatNarrative:
    """Gemma 4 (or any chat-completions server) via NARRATIVE_BASE_URL."""

    name = "openai-compat"

    def __init__(self, base_url: str, model: str, api_key: str | None = None) -> None:
        self._base = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key

    def narrate(self, live_features: dict, teams: tuple[str, str]) -> str:
        prompt = features_to_prompt(live_features, teams)
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        url = self._base if self._base.endswith("/chat/completions") else f"{self._base}/chat/completions"
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": "Annotate paper-trading intervals. Never guess a winner.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        return data["choices"][0]["message"]["content"].strip()
